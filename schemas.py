"""
Database Schemas for Dental Receptionist App

Each Pydantic model maps to a MongoDB collection (lowercased class name).
"""
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from datetime import datetime

class Patient(BaseModel):
    first_name: str = Field(..., description="Patient first name")
    last_name: str = Field(..., description="Patient last name")
    email: Optional[EmailStr] = Field(None, description="Patient email")
    phone: Optional[str] = Field(None, description="E.164 phone number if available")
    date_of_birth: Optional[str] = Field(None, description="YYYY-MM-DD")
    address: Optional[str] = Field(None, description="Mailing address")
    notes: Optional[str] = Field(None, description="Additional notes")

class Appointment(BaseModel):
    patient_id: str = Field(..., description="Reference to patient _id as string")
    reason: str = Field(..., description="Reason for visit / procedure")
    start_time: str = Field(..., description="ISO 8601 start time")
    end_time: str = Field(..., description="ISO 8601 end time")
    provider: Optional[str] = Field(None, description="Dentist/Hygienist name")
    status: str = Field("scheduled", description="scheduled|completed|cancelled|no_show|rescheduled")

class Feedback(BaseModel):
    patient_id: Optional[str] = Field(None, description="Reference to patient _id as string")
    rating: int = Field(..., ge=1, le=5, description="1-5 stars")
    comments: Optional[str] = Field(None, description="Free text feedback")
    visit_date: Optional[str] = Field(None, description="YYYY-MM-DD of visit")

# Minimal schema to store basic logs of communications if desired
class MessageLog(BaseModel):
    channel: str = Field(..., description="chat|sms|call")
    direction: str = Field(..., description="inbound|outbound")
    content: str = Field(..., description="Message content")
    user_context: Optional[dict] = Field(None, description="Optional JSON context like patient or intent")
    timestamp: Optional[datetime] = None
