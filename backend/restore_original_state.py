import sys
import os
from dotenv import load_dotenv

# Load env
base_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(base_dir, 'backend', '.env'))
load_dotenv(os.path.join(base_dir, '.env'))

sys.path.append(os.path.join(os.getcwd(), 'backend'))
from core.database import SessionLocal, TenantDB

def restore_original_state():
    db = SessionLocal()
    try:
        print("🔄 REVERTENDO todas as mudanças para o estado original...")
        
        # Restaurar wpp-osvaldo
        wpp_osvaldo = db.query(TenantDB).filter(TenantDB.id == "wpp-osvaldo").first()
        if wpp_osvaldo:
            print(f"   wpp-osvaldo: {wpp_osvaldo.instance_name} → cosmos-wpp-osvaldo")
            wpp_osvaldo.instance_name = "cosmos-wpp-osvaldo"
        
        # Restaurar cosmoserp  
        cosmoserp = db.query(TenantDB).filter(TenantDB.id == "cosmoserp").first()
        if cosmoserp:
            print(f"   cosmoserp: {cosmoserp.instance_name} → cosmos-test")
            cosmoserp.instance_name = "cosmos-test"
        
        db.commit()
        print("✅ Estado original restaurado!")
        
        # Verificar
        print("\n📋 Estado Atual:")
        for tenant in db.query(TenantDB).all():
            print(f"   {tenant.id}: {tenant.instance_name}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    restore_original_state()
