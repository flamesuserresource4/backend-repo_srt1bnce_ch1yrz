import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from bson import ObjectId
from datetime import datetime

from database import db, create_document, get_documents
from schemas import Patient, Appointment, Feedback, MessageLog

app = FastAPI(title="AI Dental Receptionist API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Utilities

def to_str_id(doc):
    if not doc:
        return doc
    if isinstance(doc, list):
        return [to_str_id(d) for d in doc]
    d = dict(doc)
    if d.get("_id"):
        d["_id"] = str(d["_id"])
    # Convert datetimes to isoformat
    for k, v in list(d.items()):
        if isinstance(v, datetime):
            d[k] = v.isoformat()
    return d

@app.get("/")
def root():
    return {"service": "AI Dental Receptionist API", "status": "ok"}

@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = getattr(db, "name", "✅ Connected")
            response["connection_status"] = "Connected"
            try:
                response["collections"] = db.list_collection_names()
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️ Connected but Error: {str(e)[:80]}"
        else:
            response["database"] = "⚠️ Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:120]}"
    return response

# Appointment endpoints

class AppointmentCreate(Appointment):
    pass

@app.post("/appointments")
def create_appointment(payload: AppointmentCreate):
    # basic overlap check for the same provider
    coll = db["appointment"]
    overlap = coll.find_one({
        "provider": payload.provider,
        "status": {"$in": ["scheduled", "rescheduled"]},
        "$or": [
            {"start_time": {"$lt": payload.end_time}, "end_time": {"$gt": payload.start_time}}
        ]
    }) if db else None
    if overlap:
        raise HTTPException(status_code=409, detail="Time slot not available")
    inserted_id = create_document("appointment", payload)
    doc = coll.find_one({"_id": ObjectId(inserted_id)}) if db else None
    return {"appointment": to_str_id(doc) if doc else {"_id": inserted_id}}

@app.get("/appointments")
def list_appointments(patient_id: Optional[str] = None, provider: Optional[str] = None, status: Optional[str] = None, limit: int = 50):
    filt = {}
    if patient_id:
        try:
            filt["patient_id"] = patient_id
        except Exception:
            pass
    if provider:
        filt["provider"] = provider
    if status:
        filt["status"] = status
    docs = get_documents("appointment", filt, limit)
    return {"appointments": to_str_id(docs)}

@app.patch("/appointments/{appointment_id}")
def update_appointment(appointment_id: str, status: Optional[str] = None, start_time: Optional[str] = None, end_time: Optional[str] = None):
    coll = db["appointment"]
    update = {}
    if status: update["status"] = status
    if start_time: update["start_time"] = start_time
    if end_time: update["end_time"] = end_time
    if not update:
        raise HTTPException(status_code=400, detail="No fields to update")
    res = coll.update_one({"_id": ObjectId(appointment_id)}, {"$set": {**update, "updated_at": datetime.utcnow()}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Appointment not found")
    doc = coll.find_one({"_id": ObjectId(appointment_id)})
    return {"appointment": to_str_id(doc)}

@app.delete("/appointments/{appointment_id}")
def cancel_appointment(appointment_id: str):
    coll = db["appointment"]
    res = coll.update_one({"_id": ObjectId(appointment_id)}, {"$set": {"status": "cancelled", "updated_at": datetime.utcnow()}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return {"ok": True}

# Patient endpoints

@app.post("/patients")
def create_patient(payload: Patient):
    inserted_id = create_document("patient", payload)
    doc = db["patient"].find_one({"_id": ObjectId(inserted_id)}) if db else None
    return {"patient": to_str_id(doc) if doc else {"_id": inserted_id}}

@app.get("/patients")
def list_patients(q: Optional[str] = None, limit: int = 50):
    filt = {}
    if q:
        filt = {"$or": [
            {"first_name": {"$regex": q, "$options": "i"}},
            {"last_name": {"$regex": q, "$options": "i"}},
            {"email": {"$regex": q, "$options": "i"}},
            {"phone": {"$regex": q, "$options": "i"}},
        ]}
    docs = get_documents("patient", filt, limit)
    return {"patients": to_str_id(docs)}

# Feedback endpoints

@app.post("/feedback")
def submit_feedback(payload: Feedback):
    inserted_id = create_document("feedback", payload)
    doc = db["feedback"].find_one({"_id": ObjectId(inserted_id)}) if db else None
    return {"feedback": to_str_id(doc) if doc else {"_id": inserted_id}}

@app.get("/feedback")
def list_feedback(limit: int = 100):
    docs = get_documents("feedback", {}, limit)
    return {"feedback": to_str_id(docs)}

# Simple chatbot endpoint for FAQ and triage (placeholder rules, no paid AI)
class ChatRequest(BaseModel):
    message: str = Field(...)

COMMON_QA = {
    "hours": "We are open Mon-Fri 8am-6pm and Sat 9am-2pm.",
    "location": "We are located at 123 Smile St, Suite 100.",
    "insurance": "We accept most major insurance plans. Please have your member ID ready.",
    "emergency": "If you are experiencing severe pain, swelling, or trauma, please call 911 or go to the nearest ER. For urgent dental issues, we can connect you to the on-call dentist.",
}

@app.post("/chat")
def chat_bot(req: ChatRequest):
    text = req.message.lower()
    reply = None
    for key, ans in COMMON_QA.items():
        if key in text:
            reply = ans
            break
    if not reply:
        reply = "Thanks for your message. I can help with hours, location, insurance, scheduling, and more."
    # log
    try:
        create_document("messagelog", MessageLog(channel="chat", direction="inbound", content=req.message))
        create_document("messagelog", MessageLog(channel="chat", direction="outbound", content=reply))
    except Exception:
        pass
    return {"reply": reply}

# Cost estimate - simple rule-based estimator (no external billing integration)
class EstimateRequest(BaseModel):
    procedure_code: str

PROCEDURE_BASE = {
    "D1110": 120.0,  # adult prophylaxis
    "D0150": 110.0,  # comprehensive oral eval
    "D0274": 85.0,   # bitewing four films
    "D2331": 180.0,  # resin composite 2 surfaces
}

@app.post("/estimate")
def estimate_cost(req: EstimateRequest):
    base = PROCEDURE_BASE.get(req.procedure_code.upper())
    if base is None:
        raise HTTPException(status_code=404, detail="Procedure not found")
    return {"procedure_code": req.procedure_code.upper(), "estimated_cost": base}

# Placeholder insurance verification endpoint (mock)
class InsuranceRequest(BaseModel):
    provider: str
    member_id: str
    dob: Optional[str] = None

@app.post("/insurance/check")
def insurance_check(req: InsuranceRequest):
    # Mock logic: if member_id ends with even digit -> eligible
    eligible = req.member_id[-1].isdigit() and int(req.member_id[-1]) % 2 == 0
    benefits = {"preventive": "80%", "basic": "60%", "major": "40%"} if eligible else {}
    return {"eligible": eligible, "benefits": benefits}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
