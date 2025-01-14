
import json
import os
from typing import List, Optional
from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import func
from app.auth.authDTO import UserToken
from app.auth.authService import generate_presigned_url, get_password_hash, get_user_current
from app.company.companyDTO import Company, CompanyCreate, CompanyInDBBaseWCount, CompanyUpdate, CompanyWCount, CompanyWCountWithRecruiter
from sqlalchemy.orm import Session
from app.company.companyService import upload_picture_to_s3
from app import deps
from models.models import CVitae, CompanyUser, UserEnum, Users
from models.models import Company as CompanyModel
from sqlalchemy.orm import aliased

companyRouter = APIRouter()
companyRouter.tags = ['Company']
fields_to_update = [
        "name", "sector", "document", "document_type", "city",
        "employees", "activeoffers", "availableoffers", "totaloffers",
        "is_deleted", "active"]
S3_BUCKET_NAME = os.getenv("BUCKET_NAME")

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

        # Check if a CompanyUser record already exists
        existing_company_user = db.query(CompanyUser).filter(
            CompanyUser.companyId == company_id,
            CompanyUser.userId == responsible_user.id
        ).first()
        if not existing_company_user:
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

        # Check if a CompanyUser record already exists
        existing_konempleo_user = db.query(CompanyUser).filter(
            CompanyUser.companyId == company_id,
            CompanyUser.userId == admin_user.id
        ).first()
        if not existing_konempleo_user:
            # Add a new CompanyUser record for the new konempleo_responsible
            new_konempleo_user = CompanyUser(companyId=company_id, userId=admin_user.id)
            db.add(new_konempleo_user)

    # Commit the changes
    db.commit()
    db.refresh(company)

    return company


@companyRouter.get("/company/owned/", status_code=200, response_model=List[CompanyWCountWithRecruiter])
def get_company(
    *, db: Session = Depends(deps.get_db), userToken: UserToken = Depends(get_user_current)
) -> List[CompanyWCountWithRecruiter]:
    """
    Gets companies owned by the user in the database along with recruiter info.
    Only includes companies that are not marked as deleted (is_deleted = False).
    """
    # Find all companies associated with the user
    company_user_records = db.query(CompanyUser).join(CompanyModel).filter(
        CompanyUser.userId == userToken.id,
        CompanyModel.is_deleted == False  # Filter out deleted companies
    ).all()

    if not company_user_records:
        raise HTTPException(status_code=404, detail="No companies found for the given user ID.")

    company_ids = [record.companyId for record in company_user_records]

    # Subquery for recruiter information
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
        Users.active == True,
        Users.is_deleted == False  # Exclude deleted recruiters
    ).subquery()

    # Main query to get companies with recruiter information
    companies_with_recruiter = db.query(
        CompanyModel,
        func.count(CVitae.Id).label('cv_count'),
        recruiter_subquery.c.recruiter_name,
        recruiter_subquery.c.recruiter_email
    ).outerjoin(
        CVitae, CVitae.companyId == CompanyModel.id
    ).outerjoin(
        recruiter_subquery, (recruiter_subquery.c.company_id == CompanyModel.id) & 
                            (recruiter_subquery.c.row_number == 1)
    ).filter(
        CompanyModel.id.in_(company_ids),
        CompanyModel.is_deleted == False  # Exclude deleted companies
    ).group_by(
        CompanyModel.id,
        recruiter_subquery.c.recruiter_name,
        recruiter_subquery.c.recruiter_email
    ).all()

    if not companies_with_recruiter:
        return []

    # Format the response
    result = []
    for company, cv_count, recruiter_name, recruiter_email in companies_with_recruiter:
        # Generate a pre-signed URL for the picture
        presigned_url = None
        if company.picture:
            object_key = company.picture.replace(f"https://{S3_BUCKET_NAME}.s3.amazonaws.com/", "")
            presigned_url = generate_presigned_url(S3_BUCKET_NAME, object_key)

        result.append(CompanyWCountWithRecruiter(
            id=company.id,
            name=company.name,
            sector=company.sector,
            document=company.document,
            document_type=company.document_type,
            city=company.city,
            picture=presigned_url,  # Use the pre-signed URL
            activeoffers=company.activeoffers,
            availableoffers=company.availableoffers,
            totaloffers=company.totaloffers,
            active=company.active,
            is_deleted=company.is_deleted,
            employees=company.employees,
            cv_count=cv_count,
            recruiter_name=recruiter_name,
            recruiter_email=recruiter_email
        ))
    
    return result


@companyRouter.get("/company/all/", status_code=200, response_model=List[CompanyWCount])
def get_all_companies(
    *, db: Session = Depends(deps.get_db), userToken: UserToken = Depends(get_user_current)
) -> List[CompanyWCount]:
    """
    Gets all companies in the database if the user is a super admin.
    Includes the first active user with role type 2 (admin) and role type 3 (company_recruit).
    Only includes companies that are not marked as deleted (is_deleted = False).
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
        Users.active == True,
        Users.is_deleted == False  # Exclude deleted admin users
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
        Users.active == True,
        Users.is_deleted == False  # Exclude deleted recruiter users
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
    ).filter(
        CompanyModel.is_deleted == False  # Exclude deleted companies
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
        # Generate a pre-signed URL for the picture
        presigned_url = None
        if company.picture:
            object_key = company.picture.replace(f"https://{S3_BUCKET_NAME}.s3.amazonaws.com/", "")
            presigned_url = generate_presigned_url(S3_BUCKET_NAME, object_key)

        if company.id not in result_dict:
            result_dict[company.id] = CompanyWCount(
                id=company.id,
                name=company.name,
                sector=company.sector,
                document=company.document,
                document_type=company.document_type,
                city=company.city,
                picture=presigned_url,  # Use the pre-signed URL
                activeoffers=company.activeoffers,
                availableoffers=company.availableoffers,
                totaloffers=company.totaloffers,
                active=company.active,
                is_deleted=company.is_deleted,
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

@companyRouter.get("/company/{company_id}", status_code=200, response_model=CompanyInDBBaseWCount)
def get_company_by_id(
    company_id: int,
    db: Session = Depends(deps.get_db),
    userToken: UserToken = Depends(get_user_current)
) -> CompanyInDBBaseWCount:
    """
    Get a specific company by its ID along with admin info, recruiter info, and CV count.
    Only includes companies that are not marked as deleted (is_deleted = False).
    """

    # Subquery for admin information
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
        Users.active == True,
        Users.is_deleted == False  # Exclude deleted admin users
    ).subquery()

    # Subquery for recruiter information
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
        Users.active == True,
        Users.is_deleted == False  # Exclude deleted recruiters
    ).subquery()

    # Query to get the company with admin, recruiter, and CV count information
    company_with_details = db.query(
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
    ).filter(
        CompanyModel.id == company_id,
        CompanyModel.is_deleted == False  # Exclude deleted companies
    ).group_by(
        CompanyModel.id,
        admin_subquery.c.admin_name, admin_subquery.c.admin_email,
        recruiter_subquery.c.recruiter_name, recruiter_subquery.c.recruiter_email
    ).first()

    if not company_with_details:
        raise HTTPException(status_code=404, detail="Company not found.")

    # Extract company details
    company, cv_count, admin_name, admin_email, recruiter_name, recruiter_email = company_with_details

    # Generate a pre-signed URL for the picture
    presigned_url = None
    if company.picture:
        object_key = company.picture.replace(f"https://{S3_BUCKET_NAME}.s3.amazonaws.com/", "")
        presigned_url = generate_presigned_url(S3_BUCKET_NAME, object_key)

    # Format the response
    return CompanyWCountWithRecruiter(
        id=company.id,
        name=company.name,
        sector=company.sector,
        document=company.document,
        document_type=company.document_type,
        city=company.city,
        picture=presigned_url,  # Use the pre-signed URL
        activeoffers=company.activeoffers,
        availableoffers=company.availableoffers,
        totaloffers=company.totaloffers,
        active=company.active,
        is_deleted=company.is_deleted,
        employees=company.employees,
        cv_count=cv_count,
        admin_name=admin_name,
        admin_email=admin_email,
        recruiter_name=recruiter_name,
        recruiter_email=recruiter_email
    )