
import json
from typing import List, Optional
from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import func
from app.auth.authDTO import UserToken
from app.auth.authService import get_password_hash, get_user_current
from app.company.companyDTO import Company, CompanyCreate, CompanyUpdate, CompanyWCount
from sqlalchemy.orm import Session
from app.company.companyService import upload_picture_to_s3
from app import deps
from models.models import CVitae, CompanyUser, UserEnum, Users
from models.models import Company as CompanyModel
from sqlalchemy.orm import aliased

companyRouter = APIRouter()
companyRouter.tags = ['Company']
fields_to_update = [
    'name', 
    'sector', 
    'document', 
    'document_type', 
    'city', 
    'employees', 
    'activeoffers', 
    'totaloffers'
]

@companyRouter.post("/company/", status_code=201, response_model=Company)
def create_company(
    *, company_in: str = Form(...), 
    picture: Optional[UploadFile] = File(None),
    db: Session = Depends(deps.get_db), userToken: UserToken = Depends(get_user_current)
) -> dict:
    """
    Create a new company in the database.
    """

    company_create = json.loads(company_in)  # Parse the form-data string into a dictionary
    company_in = CompanyCreate(**company_create)

    if userToken.role not in [UserEnum.super_admin, UserEnum.admin]:
        raise HTTPException(status_code=403, detail="No tiene los permisos para ejecutar este servicio")
    
    activeState = userToken.role == UserEnum.super_admin

    try:
        # Step 1: Insert user (responsible_user)
        user = Users(
            fullname=company_in.responsible_user.fullname,
            email=company_in.responsible_user.email,
            password=get_password_hash('deeptalentUser'),
            phone=company_in.responsible_user.phone,
            role=3  # Assuming this is the "company" user role
        )
        db.add(user)
        db.flush()

        # Step 2: Validate konempleo_responsible
        konempleo_user = db.query(Users).filter(Users.id == company_in.konempleo_responsible).first()
        if not konempleo_user or konempleo_user.role != UserEnum.admin:
            raise HTTPException(status_code=400, detail="The konempleo_responsible user must have the admin role.")

        # Step 3: Prepare and insert company data
        company_data = company_in.dict()

        # Remove unnecessary fields from the company data
        company_data.pop('konempleo_responsible', None)
        company_data.pop('responsible_user', None)

        # Insert the company record
        company = CompanyModel(**company_data)
        company.active = activeState

        db.add(company)
        db.flush()

        # Step 4: Insert company-user relationships
        company_user = CompanyUser(
            companyId=company.id,
            userId=user.id
        )
        konempleo_user = CompanyUser(
            companyId=company.id,
            userId=konempleo_user.id
        )
        db.add(company_user)
        db.add(konempleo_user)

        # Step 5: Commit the database transaction first
        db.commit()
        db.refresh(company)

        # Step 6: Upload picture to S3 after database transaction is successful
        if picture:
            try:
                picture_url = upload_picture_to_s3(picture, company_in.name)
                company.picture = picture_url
                db.commit()  # Commit the update to store the picture URL
            except Exception as e:
                print(f"Warning: Failed to upload picture to S3. Reason: {str(e)}")

        return company

    except Exception as e:
        # If any operation fails, rollback the transaction
        db.rollback()
        raise HTTPException(status_code=500, detail=f"An error occurred while creating the company: {str(e)}")

    
@companyRouter.put("/company/{company_id}", response_model=Company)
def update_company(
    company_id: int,
    company_in: CompanyUpdate = Body(...),
    db: Session = Depends(deps.get_db),
    userToken: UserToken = Depends(get_user_current)
) -> dict:
    """
    Update a company in the database.
    """

    # Check if the user has sufficient permissions
    if userToken.role not in [UserEnum.super_admin, UserEnum.admin]:
        raise HTTPException(status_code=403, detail="No tiene los permisos para ejecutar este servicio")

    # Fetch the company by ID
    company = db.query(CompanyModel).filter(CompanyModel.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    # Update company fields
    for field in fields_to_update:
        value = getattr(company_in, field, None)
        if value is not None:
            setattr(company, field, value)

    # Handle responsible_user update (role = company)
    if company_in.responsible_user:
        # Check if the new responsible user already exists
        responsible_user = db.query(Users).filter(Users.email == company_in.responsible_user.email).first()

        # Find the current responsible user for this company
        current_responsible_user_record = db.query(CompanyUser).join(Users).filter(
            CompanyUser.companyId == company_id,
            Users.role == UserEnum.company
        ).first()

        if current_responsible_user_record:
            current_responsible_user = db.query(Users).filter(Users.id == current_responsible_user_record.userId).first()

            # If the new responsible user is different from the current one, deactivate the old one and remove the CompanyUser record
            if current_responsible_user and current_responsible_user.email != company_in.responsible_user.email:
                # Deactivate the old responsible user
                current_responsible_user.active = False
                db.add(current_responsible_user)
                
                # Remove the old CompanyUser record
                db.delete(current_responsible_user_record)

        # Create a new responsible user if they don't already exist
        if not responsible_user:
            new_user = Users(
                fullname=company_in.responsible_user.fullname,
                email=company_in.responsible_user.email,
                password=get_password_hash('deeptalentUser'),
                phone=company_in.responsible_user.phone,
                role=UserEnum.company
            )
            db.add(new_user)
            db.flush()  # Get the new user ID
            responsible_user = new_user

        # Add a new CompanyUser record for the new responsible user
        new_company_user = CompanyUser(companyId=company_id, userId=responsible_user.id)
        db.add(new_company_user)

    # Handle konempleo_responsible update (role = admin)
    if company_in.konempleo_responsible:
        admin_user = db.query(Users).filter(Users.id == company_in.konempleo_responsible).first()
        if not admin_user or admin_user.role != UserEnum.admin:
            raise HTTPException(status_code=400, detail="Invalid admin user")

        # Find the current konempleo_responsible record
        current_konempleo_record = db.query(CompanyUser).join(Users).filter(
            CompanyUser.companyId == company_id,
            Users.role == UserEnum.admin
        ).first()

        # Remove the old CompanyUser record if it's different from the new one
        if current_konempleo_record and current_konempleo_record.userId != company_in.konempleo_responsible:
            db.delete(current_konempleo_record)

        # Add a new CompanyUser record for the new konempleo_responsible
        new_konempleo_user = CompanyUser(companyId=company_id, userId=admin_user.id)
        db.add(new_konempleo_user)

    # Commit the changes
    db.commit()
    db.refresh(company)

    return company


@companyRouter.get("/company/owned/", status_code=200, response_model=List[CompanyWCount])
def get_company(
    *, db: Session = Depends(deps.get_db), userToken: UserToken = Depends(get_user_current)
) -> dict:
    """
    gets company in the database.
    """
    company_user_records = db.query(CompanyUser).filter(CompanyUser.userId == userToken.id).all()
    
    if not company_user_records:
        raise HTTPException(status_code=404, detail="No companies found for the given user ID.")
    
    company_ids = [record.companyId for record in company_user_records]

    # Query to get all companies and count of CVitae records for each company
    companies_with_cv_count = db.query(
        CompanyModel,
        func.count(CVitae.Id).label('cv_count')
    ).outerjoin(
        CVitae, CVitae.companyId == CompanyModel.id
    ).filter(
        CompanyModel.id.in_(company_ids)
    ).group_by(
        CompanyModel.id
    ).all()

    if not companies_with_cv_count:
        return []
        # raise HTTPException(status_code=404, detail="No companies found.")
    
    # Format the response to include the company data along with the CV count
    result = []
    for company, cv_count in companies_with_cv_count:
        company_dict = company.__dict__.copy()
        company_dict['cv_count'] = cv_count
        result.append(company_dict)
    
    return result


@companyRouter.get("/company/all/", status_code=200, response_model=List[CompanyWCount])
def get_all_companies(
    *, db: Session = Depends(deps.get_db), userToken: UserToken = Depends(get_user_current)
) -> List[CompanyWCount]:
    """
    Gets all companies in the database if the user is a super admin.
    Includes the first active user with role type 2 (admin) and role type 3 (company_recruit).
    """
    if userToken.role != UserEnum.super_admin:
        raise HTTPException(status_code=403, detail="You do not have permission to view all companies.")

    # Subquery for first admin user
    admin_subquery = db.query(
        CompanyUser.companyId.label("company_id"),
        Users.fullname.label("admin_name"),
        Users.email.label("admin_email"),
        func.row_number().over(
            partition_by=CompanyUser.companyId, 
            order_by=Users.id
        ).label("row_number")
    ).join(
        Users, Users.id == CompanyUser.userId
    ).filter(
        Users.role == UserEnum.admin,
        Users.active == True
    ).subquery()

    # Subquery for first recruiter user
    recruiter_subquery = db.query(
        CompanyUser.companyId.label("company_id"),
        Users.fullname.label("recruiter_name"),
        Users.email.label("recruiter_email"),
        func.row_number().over(
            partition_by=CompanyUser.companyId, 
            order_by=Users.id
        ).label("row_number")
    ).join(
        Users, Users.id == CompanyUser.userId
    ).filter(
        Users.role == UserEnum.company,
        Users.active == True
    ).subquery()

    # Main query
    companies_with_details = db.query(
        CompanyModel,
        func.count(CVitae.Id).label('cv_count'),
        admin_subquery.c.admin_name,
        admin_subquery.c.admin_email,
        recruiter_subquery.c.recruiter_name,
        recruiter_subquery.c.recruiter_email
    ).outerjoin(
        CVitae, CVitae.companyId == CompanyModel.id
    ).outerjoin(
        admin_subquery, (admin_subquery.c.company_id == CompanyModel.id) & 
                        (admin_subquery.c.row_number == 1)
    ).outerjoin(
        recruiter_subquery, (recruiter_subquery.c.company_id == CompanyModel.id) & 
                            (recruiter_subquery.c.row_number == 1)
    ).group_by(
        CompanyModel.id,
        admin_subquery.c.admin_name, admin_subquery.c.admin_email,
        recruiter_subquery.c.recruiter_name, recruiter_subquery.c.recruiter_email
    ).all()

    if not companies_with_details:
        return []

    # Combine results into a single entry per company
    result_dict = {}
    for company, cv_count, admin_name, admin_email, recruiter_name, recruiter_email in companies_with_details:
        if company.id not in result_dict:
            result_dict[company.id] = CompanyWCount(
                id=company.id,
                name=company.name,
                sector=company.sector,
                document=company.document,
                document_type=company.document_type,
                city=company.city,
                picture=company.picture,
                activeoffers=company.activeoffers,
                availableoffers=company.availableoffers,
                totaloffers=company.totaloffers,
                active=company.active,
                employees=company.employees,
                cv_count=cv_count,
                admin_name=admin_name,
                admin_email=admin_email,
                recruiter_name=recruiter_name,
                recruiter_email=recruiter_email
            )
        else:
            # Update recruiter or admin data if it was missing in previous rows
            if not result_dict[company.id].admin_name and admin_name:
                result_dict[company.id].admin_name = admin_name
                result_dict[company.id].admin_email = admin_email
            if not result_dict[company.id].recruiter_name and recruiter_name:
                result_dict[company.id].recruiter_name = recruiter_name
                result_dict[company.id].recruiter_email = recruiter_email

    # Convert dictionary to a list of results
    return list(result_dict.values())