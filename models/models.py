from sqlalchemy import ARRAY, TIMESTAMP, Boolean, Column, Date, DateTime, Enum, Float, ForeignKey, Integer, String, Text, func, text
from sqlalchemy.orm import relationship
from enum import IntEnum

from db.base_class import Base

class UserEnum(IntEnum):
    super_admin = 1
    admin = 2
    company = 3
    company_recruit = 4
    integrations = 5

class contractEnum(IntEnum):
    termino_fijo = 1
    termino_indefinido = 2
    obra_o_labor = 3
    prestacion_servicios = 4
    practicas = 5
    freelance = 6

class OfferTypeEnum(IntEnum):
    presencial = 1
    remoto = 2
    hibrido = 3


class ShiftEnum(IntEnum):
    lv = 1  # L - V
    ls = 2  # L - S
    rotativo = 3  # Rotativo
    por_definir = 4  # Por definir

class genderEnum(IntEnum):
    male = 1
    female = 2
    other = 3

class militaryEnum(IntEnum):
    yes = 1
    no = 2
    NA = 3

class ExperienceYearsEnum(IntEnum):
    sin_experiencia = 0
    seis_meses = 1
    un_ano = 2
    dos_anos = 3
    tres_anos = 4
    mas_de_tres_anos = 5

class EducationEnum(IntEnum):
    primaria = 1
    bachillerato = 2
    tecnico = 3
    tecnologo = 4
    universitario = 5
    posgrado = 6


class Company(Base):
    __tablename__ = 'company'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    sector = Column(String)
    document = Column(String, nullable=False, unique=True)
    document_type = Column(String)
    picture = Column(String)
    activeoffers = Column(Integer, server_default=text('0'))
    availableoffers = Column(Integer, server_default=text('0'))
    totaloffers = Column(Integer, server_default=text('0'))
    employees = Column(Integer, server_default=text('0'))
    city = Column(String)
    active = Column(Boolean, default=True)
    is_deleted = Column(Boolean, nullable=False, server_default='false')

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
    cvtext = Column(Text)
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
    background_date = Column(Date, nullable=True)

    vitae_company = relationship('Company', back_populates='company_cvs')
    Vitae_offers = relationship('VitaeOffer', back_populates='cvitae')

class Offer(Base):
    __tablename__ = 'offers'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    duties = Column(String)
    exp_area = Column(String)
    vacants = Column(Integer)
    contract_type = Column(Enum(contractEnum, native_enum=False), nullable=True)
    salary = Column(String)
    city = Column(Integer)
    shift = Column(Enum(ShiftEnum), nullable=True)
    gender = Column(Enum(genderEnum))
    military_notebook = Column(Enum(militaryEnum))
    age = Column(String)
    job_type = Column(String)
    license = Column(ARRAY(String), default=["No Aplica"], nullable=False)
    disabled = Column(Boolean, default=False)
    experience_years = Column(Enum(ExperienceYearsEnum), nullable=True)
    offer_type = Column(Enum(OfferTypeEnum), nullable=True)
    ed_required = Column(Enum(EducationEnum), nullable=True)
    cargoId = Column(Integer, ForeignKey('cargo.id'))
    offer_owner = Column(Integer, ForeignKey('users.id'), nullable=False)
    assigned_cvs = Column(Integer, server_default=text('0'))
    filter_questions = Column(String)
    active = Column(Boolean, default=True)
    created_date = Column(DateTime, server_default=func.now(), nullable=False)
    modified_date = Column(DateTime, onupdate=func.now(), server_default=func.now(), nullable=False)
    contacted = Column(Integer, default=0)
    interested = Column(Integer, default=0)

    
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
    is_deleted = Column(Boolean, nullable=False, server_default='false')

    companies = relationship("CompanyUser", back_populates="user")

class VitaeOffer(Base):
    __tablename__ = 'vitaeOffer'

    id = Column(Integer, primary_key=True)
    cvitaeId = Column(Integer, ForeignKey('cvitae.Id'), nullable=False)
    offerId = Column(Integer, ForeignKey('offers.id'), nullable=False)
    status = Column(Enum('pending', 'hired', 'error_processing', 'rejected', name='status_enum'))
    ai_response = Column(Text)
    response_score = Column(Float)
    whatsapp_status = Column(Enum('notsent', 'pending_response', 'interested', 'not_interested', name='whatsapp_status_enum'))
    smartdataId = Column(String)
    comments = Column(String(160))
    created_date = Column(DateTime, server_default=func.now(), nullable=False)
    modified_date = Column(DateTime, onupdate=func.now(), server_default=func.now(), nullable=False)

    cvitae = relationship('CVitae', back_populates='Vitae_offers')
    offer = relationship('Offer', back_populates='vitae_offers')