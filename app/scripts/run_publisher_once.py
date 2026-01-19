from app.database import SessionLocal
from app.services.publisher_worker import publish_due

def main():
    db = SessionLocal()
    try:
        res = publish_due(db, limit=50)
        print(res)
    finally:
        db.close()

if __name__ == "__main__":
    main()
