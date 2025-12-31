from app.db.session import SessionLocal
from app.db.models.airline import Airline

AIRLINES = [
    "Saudia",
    "flynas",
    "Emirates",
    "Qatar Airways",
    "Etihad Airways",
    "Oman Air",
    "Gulf Air",
    "Kuwait Airways",
    "Air Arabia",
    "Jazeera Airways",
    "Turkish Airlines",
    "EgyptAir",
    "Pakistan International Airlines (PIA)",
    "Biman Bangladesh Airlines",
    "Air India",
    "IndiGo",
    "SpiceJet",
    "Vistara",
    "SriLankan Airlines",
    "Malaysia Airlines",
]

def upsert_airline(db, name: str):
    name = (name or "").strip()
    if not name:
        return

    existing = db.query(Airline).filter(Airline.name == name).first()
    if existing:
        return existing

    row = Airline(name=name)
    db.add(row)
    return row

def main():
    db = SessionLocal()
    try:
        for name in AIRLINES:
            upsert_airline(db, name)

        db.commit()

        count = db.query(Airline).count()
        print(f"✅ Seed complete. Total airlines in DB: {count}")
    except Exception as e:
        db.rollback()
        print("❌ Seed failed:", e)
        raise
    finally:
        db.close()

if __name__ == "__main__":
    main()
