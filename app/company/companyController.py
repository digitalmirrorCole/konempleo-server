
from typing import List, Optional
from fastapi import APIRouter, Body, Depends, File, HTTPException, UploadFile
from fastapi.encoders import jsonable_encoder
from sqlalchemy import func
from app.auth.authDTO import UserToken
from app.auth.authService import get_password_hash, get_user_current
from app.company.companyDTO import Company, CompanyCreate, CompanyUpdate, CompanyWCount
from sqlalchemy.orm import Session
from app.company.companyService import company, upload_picture_to_s3
from app import deps
from models.models import CVitae, CompanyUser, UserEnum, Users
from models.models import Company as CompanyModel



companyRouter = APIRouter()
companyRouter.tags = ['Company']

@companyRouter.post("/company/", status_code=201, response_model=Company)
def create_company(
    *, company_in: CompanyCreate= Body(...), 
    ## picture: Optional[UploadFile] = File(None),
    db: Session = Depends(deps.get_db), userToken: UserToken = Depends(get_user_current)
) -> dict:
    """
    Create a new company in the database.
    """

    if userToken.role not in [UserEnum.super_admin, UserEnum.admin]:
        raise HTTPException(status_code=403, detail="No tiene los permisos para ejecutar este servicio")
    
    activeState = userToken.role == UserEnum.super_admin

    try:
        user = Users(
            fullname= company_in.responsible_user.fullname,
            email= company_in.responsible_user.email,
            password= get_password_hash('deeptalentUser'),
            phone= company_in.responsible_user.phone,
            role= 3
        )
        
        db.add(user)
        db.flush()

        ## picture_url = upload_picture_to_s3(picture)
        picture_url = 'aqui iria la url generada por s3'

        konempleo_userId = company_in.konempleo_responsible 

        company_data = company_in.dict()
        # company_data.pop('konempleo_responsible', None)
        company_data.pop('responsible_user', None)
        company = CompanyModel(**company_data)

        company.picture = picture_url
        company.active = activeState
        db.add(company)
        db.flush()

        company_user = CompanyUser(
            companyId=company.id,
            userId=user.id
        )
        konempleo_user = CompanyUser(
            companyId=company.id,
            userId=konempleo_userId
        )
        db.add(company_user)
        db.add(konempleo_user)

        db.commit()
        db.refresh(company)

        return company

    except Exception as e:
        # If any operation fails, the transaction is rolled back automatically
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
    if userToken.role not in [UserEnum.super_admin]:
        raise HTTPException(status_code=403, detail="No tiene los permisos para ejecutar este servicio")

    # Fetch the company by ID
    company = db.query(CompanyModel).filter(CompanyModel.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    # Update company fields
    if company_in.name is not None:
        company.name = company_in.name
    if company_in.sector is not None:
        company.sector = company_in.sector
    if company_in.document is not None:
        company.document = company_in.document
    if company_in.document_type is not None:
        company.document_type = company_in.document_type
    if company_in.city is not None:
        company.city = company_in.city
    if company_in.employees is not None:
        company.employees = company_in.employees
    if company_in.activeoffers is not None:
        company.activeoffers = company_in.activeoffers
    if company_in.totaloffers is not None:
        company.totaloffers = company_in.totaloffers

    # Handle responsible_user or konempleo_responsible update based on the role
    if company_in.responsible_user or company_in.konempleo_responsible:
        
        # Handle responsible_user update (role = company)
        if company_in.responsible_user:
            # Check if the user already exists
            responsible_user = db.query(Users).filter(Users.email == company_in.responsible_user.email).first()

            # If a responsible user is being replaced, deactivate the old one (but only the one we are replacing, not others)
            old_responsible_user = db.query(CompanyUser).join(Users).filter(
                CompanyUser.companyId == company_id,
                Users.role == UserEnum.company,
                CompanyUser.userId == responsible_user.id  # Use the ID from the matched responsible_user
            ).first()
            
            if old_responsible_user:
                old_user = db.query(Users).filter(Users.id == old_responsible_user.userId).first()
                if old_user:
                    old_user.active = False
                    db.add(old_user)

            # Add or update new responsible user
            if not responsible_user:
                new_user = Users(
                    fullname=company_in.responsible_user.fullname,
                    email=company_in.responsible_user.email,
                    password=get_password_hash('deeptalentUser'),
                    phone=company_in.responsible_user.phone,
                    role=UserEnum.company
                )
                db.add(new_user)
                db.flush()  # Flush to get new user ID
                responsible_user = new_user

            # Update the relationship in CompanyUser
            new_company_user = CompanyUser(companyId=company_id, userId=responsible_user.id)
            db.add(new_company_user)

        # Handle konempleo_responsible update (role = admin)
        if company_in.konempleo_responsible:
            admin_user = db.query(Users).filter(Users.id == company_in.konempleo_responsible).first()
            if not admin_user or admin_user.role != UserEnum.admin:
                raise HTTPException(status_code=400, detail="Invalid admin user")

            # Update the previous konempleo_responsible user and deactivate them
            old_konempleo = db.query(CompanyUser).filter(
                CompanyUser.companyId == company_id, 
                Users.role == UserEnum.admin
            ).first()
            if old_konempleo:
                old_admin = db.query(Users).filter(Users.id == old_konempleo.userId).first()
                if old_admin:
                    old_admin.active = False
                    db.add(old_admin)

            # Add the new admin user as the konempleo_responsible
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
        raise HTTPException(status_code=404, detail="No companies found.")
    
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
    """
    if userToken.role != UserEnum.super_admin:
        raise HTTPException(status_code=403, detail="You do not have permission to view all companies.")

    # Query to get all companies and count of CVitae records for each company
    companies_with_cv_count = db.query(
        CompanyModel,
        func.count(CVitae.Id).label('cv_count')
    ).outerjoin(
        CVitae, CVitae.companyId == CompanyModel.id
    ).group_by(
        CompanyModel.id
    ).all()

    if not companies_with_cv_count:
        raise HTTPException(status_code=404, detail="No companies found.")
    
    # Format the response to include the company data along with the CV count
    result = []
    for company, cv_count in companies_with_cv_count:
        company_dict = company.__dict__.copy()
        company_dict['cv_count'] = cv_count
        result.append(CompanyWCount(**company_dict))
    
    return result
