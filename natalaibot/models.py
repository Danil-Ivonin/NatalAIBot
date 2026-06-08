from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Gender = Literal["male", "female"]
GenerationStatus = Literal["pending", "processing", "completed", "failed"]


class GeoPoint(BaseModel):
    model_config = ConfigDict(extra="ignore")

    addr: str
    lat: float
    lng: float
    city: str
    nation: str
    timezone: str


class ReportSection(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str
    text: str


class StyledNatalReport(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str
    intro: ReportSection
    general: ReportSection
    love_and_sex: ReportSection
    career_and_money: ReportSection
    demons: ReportSection
    final_summary: ReportSection


class ChartImage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    url: str
    mime_type: str


class Character(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    name: str
    slug: str
    description: str | None = None
    is_active: bool = True


class GenerationCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    person_name: str | None = None
    gender: Gender | None = None
    birth_date: str
    birth_time: str
    birth_place: GeoPoint
    persona_id: str


class GenerationCreated(BaseModel):
    model_config = ConfigDict(extra="ignore")

    generation_id: str
    status: GenerationStatus


class GenerationRead(BaseModel):
    model_config = ConfigDict(extra="ignore")

    generation_id: str
    status: GenerationStatus
    result_text: StyledNatalReport | None = None
    chart_image: ChartImage | None = None
    error_message: str | None = None
    created_at: str | None = None
    completed_at: str | None = None


class PersonCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    person_name: str | None = None
    gender: Gender | None = None
    birth_date: str
    birth_time: str
    birth_place: GeoPoint


class PersonRead(PersonCreate):
    person_id: str


class PersonsPage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    items: list[PersonRead]
    total: int = 0


class GenerationLinkCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    generation_id: str


class GenerationLinkRead(BaseModel):
    model_config = ConfigDict(extra="ignore")

    generation_id: str
    created_at: str | None = None


class GenerationLinksPage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    items: list[GenerationLinkRead]
    total: int = 0


class UserBirthData(BaseModel):
    person_name: str | None = None
    gender: Gender | None = None
    birth_date: str
    birth_time: str
    birth_place: GeoPoint
    persona_id: str = Field(min_length=1)
