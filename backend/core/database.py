import os
from typing import Optional, Dict
from sqlalchemy import create_engine, Column, String, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base, relationship, joinedload
from sqlalchemy.sql import func

# Configuração do Banco
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=20, max_overflow=30)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# --- MODELOS ---

class TenantDB(Base):
    __tablename__ = "tenants"
    __table_args__ = {"schema": "public"}

    id = Column(String, primary_key=True)  # Ex: 'empresa-x'
    name = Column(String)
    instance_name = Column(String)  # Ex: 'cosmos-empresa-x'
    instance_id = Column(String)
    instance_token = Column(String)
    webhook_url = Column(String)
    type = Column(String, default="CLIENT")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relacionamento com usuários
    users = relationship("UserDB", back_populates="tenant")


class UserDB(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": "public"}

    username = Column(String, primary_key=True, index=True)
    full_name = Column(String)
    hashed_password = Column(String)
    disabled = Column(Boolean, default=False)

    # Vinculo com a empresa
    tenant_id = Column(String, ForeignKey("public.tenants.id"))
    tenant = relationship("TenantDB", back_populates="users")


# Criação das tabelas (se não existirem)
try:
    Base.metadata.create_all(bind=engine)
except Exception as e:
    print(f"Erro no create_all (pode ignorar se já existem): {e}")


# --- FUNÇÕES AUXILIARES ---

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_user_with_tenant(username: str):
    """Busca usuário e já traz os dados da empresa/instância junto"""
    db = SessionLocal()
    try:
        # O joinedload avisa: "Traga o tenant AGORA, não deixe para depois"
        user = db.query(UserDB).options(joinedload(UserDB.tenant)).filter(UserDB.username == username).first()
        if user:
            return user
        return None
    finally:
        db.close()


def create_tenant_and_user(tenant_data: dict, user_data: dict):
    """Cria empresa e usuário numa transação atômica"""
    db = SessionLocal()
    try:
        # 1. Cria Tenant
        new_tenant = TenantDB(**tenant_data)
        db.add(new_tenant)

        # 2. Cria Usuário
        new_user = UserDB(**user_data)
        db.add(new_user)

        db.commit()
        return True
    except Exception as e:
        db.rollback()
        print(f"❌ Erro ao criar tenant/user: {e}")
        return False
    finally:
        db.close()