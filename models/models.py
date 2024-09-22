from sqlalchemy import TIMESTAMP, Boolean, Column, Enum, Float, ForeignKey, Integer, String, Text, func, text
from sqlalchemy.orm import relationship
from enum import IntEnum

from db.base_class import Base

class UserEnum(IntEnum):
    super_admin = 1
    admin = 2
    company = 3
    company_recruit = 4

class contractEnum(IntEnum):
    full_time = 1
    part_time = 2

class shiftEnum(IntEnum):
    morning = 1
    evening = 2
    night = 3

class genderEnum(IntEnum):
    male = 1
    female = 2
    other = 3

class militaryEnum(IntEnum):
    yes = 1
    no = 2
    NA = 3

class licenseEnum(IntEnum):
    required = 1
    not_required = 2

class educationEnum(IntEnum):
    none = 1
    high_school = 2
    bachelor = 3
    master = 4
    doctorate = 5

class Company(Base):
    __tablename__ = 'company'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    sector = Column(String)
    document = Column(String)
    document_type = Column(String)
    picture = Column(String)
    activeoffers = Column(Integer, server_default=text('0'))
    totaloffers = Column(Integer, server_default=text('0'))
    employees = Column(Integer, server_default=text('0'))
    city = Column(String)
    active = Column(Boolean, default=True)

    users = relationship("CompanyUser", back_populates="company")
    company_cvs = relationship("CVitae", back_populates="vitae_company")
    company_offers = relationship("CompanyOffer", back_populates="company")
    
class CompanyUser(Base):
    __tablename__ = 'companyUsers'

    id = Column(Integer, primary_key=True)
    companyId = Column(Integer, ForeignKey('company.id'), nullable=False)
    userId = Column(Integer, ForeignKey('users.id'), nullable=False)

    company = relationship('Company', back_populates='users')
    user = relationship("Users", back_populates="companies")

class CompanyOffer(Base):
    __tablename__ = 'companyOffers'

    id = Column(Integer, primary_key=True)
    companyId = Column(Integer, ForeignKey('company.id'), nullable=False)
    offerId = Column(Integer, ForeignKey('offers.id'), nullable=False)

    company = relationship('Company', back_populates='company_offers')
    offer = relationship('Offer', back_populates='company_offers')

class CVitae(Base):
    __tablename__ = 'cvitae'

    Id = Column(Integer, primary_key=True)
    url = Column(String)
    size = Column(Float)
    extension = Column(String)
    active = Column(Boolean, default=True)
    candidate_dni = Column(String)
    candidate_dni_type = Column(String)
    candidate_name = Column(String)
    candidate_phone = Column(String)
    candidate_mail = Column(String)
    candidate_city = Column(String)
    background_check = Column(String)
    tusdatos_id = Column(String)
    companyId = Column(Integer, ForeignKey('company.id'), nullable=False)

    vitae_company = relationship('Company', back_populates='company_cvs')
    Vitae_offers = relationship('VitaeOffer', back_populates='cvitae')

class Offer(Base):
    __tablename__ = 'offers'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    duties = Column(String)
    exp_area = Column(String)
    vacants = Column(Integer)
    contract_type = Column(Enum(contractEnum))
    salary = Column(String)
    city = Column(Integer)
    shift = Column(Enum(shiftEnum))
    gender = Column(Enum(genderEnum))
    military_notebook = Column(Enum(militaryEnum))
    age = Column(String)
    job_type = Column(String)
    license = Column(Enum(licenseEnum))
    disabled = Column(Boolean, default=False)
    experience_years = Column(Integer)
    offer_type = Column(String)
    whatsapp_message = Column(String)
    ed_required = Column(Enum(educationEnum))
    cargoId = Column(Integer, ForeignKey('cargo.id'))
    offer_owner = Column(Integer, ForeignKey('user.id'))
    assigned_cvs = Column(Integer, server_default=text('0'))
    filter_questions = Column(String)

    
    offer_skills = relationship('OfferSkill', back_populates='offer')
    vitae_offers = relationship('VitaeOffer', back_populates='offer')
    company_offers = relationship("CompanyOffer", back_populates="offer")

class OfferSkill(Base):
    __tablename__ = 'offerSkills'

    id = Column(Integer, primary_key=True)
    offerId = Column(Integer, ForeignKey('offers.id'), nullable=False)
    skillId = Column(Integer, ForeignKey('skills.id'), nullable=False)

    offer = relationship('Offer', back_populates='offer_skills')
    skill = relationship('Skill')

class Cargo(Base):
    __tablename__ = 'cargo'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)

    cargo_skills = relationship('CargoSkill', back_populates='cargo')

class CargoSkill(Base):
    __tablename__ = 'cargoSkills'

    id = Column(Integer, primary_key=True)
    cargoId = Column(Integer, ForeignKey('cargo.id'), nullable=False)
    skillId = Column(Integer, ForeignKey('skills.id'), nullable=False)

    cargo = relationship('Cargo', back_populates='cargo_skills')
    skill = relationship('Skill')

class Skill(Base):
    __tablename__ = 'skills'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)

class Users(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    fullname = Column(String, nullable=False)
    email = Column(String, nullable=False)
    role = Column(Enum(UserEnum), nullable=False)
    active = Column(Boolean, default=True)
    suspended = Column(Boolean, default=False)
    phone = Column(String, nullable=True)
    password = Column(String, nullable=False)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())
    must_change_password = Column(Boolean, default=True)

    companies = relationship("CompanyUser", back_populates="user")

class VitaeOffer(Base):
    __tablename__ = 'vitaeOffer'

    id = Column(Integer, primary_key=True)
    cvitaeId = Column(Integer, ForeignKey('cvitae.Id'), nullable=False)
    offerId = Column(Integer, ForeignKey('offers.id'), nullable=False)
    status = Column(Enum('pending', 'accepted', 'rejected', name='status_enum'))
    ai_response = Column(Text)
    response_score = Column(Float)
    whatsapp_status = Column(Enum('sent', 'delivered', 'read', name='whatsapp_status_enum'))

    cvitae = relationship('CVitae', back_populates='Vitae_offers')
    offer = relationship('Offer', back_populates='vitae_offers')