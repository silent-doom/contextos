"""Small request models shared by HTTP and MCP."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

Role = Literal['pm', 'architect', 'developer', 'qa', 'security']


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class NewProject(Input):
    name: str = Field(min_length=1, max_length=120)
    project_type: str = Field(min_length=1, max_length=80)
    description: str = Field(default='', max_length=1500)


class ProjectUpdate(NewProject):
    expected_version: int = Field(ge=1)
    admin: str = Field(min_length=1, max_length=128)
    archived: bool = False


class Relationship(Input):
    target_id: str = Field(min_length=1, max_length=80)
    kind: Literal['depends_on', 'references'] = 'depends_on'


class NewContext(Input):
    name: str | None = Field(default=None, min_length=1, max_length=120, description='Human-readable context name shown in the graph and reader. Separate from filename.')
    filename: str = Field(min_length=4, max_length=100)
    content: str = Field(min_length=1, max_length=10000)
    owner: str = Field(min_length=1, max_length=128)
    owner_type: Role
    relationships: list[Relationship] = Field(default_factory=list, max_length=30)
    reason: str = Field(min_length=1, max_length=1500)


class Update(NewContext):
    expected_version: int = Field(ge=1)


class Delete(Input):
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=1500)


class Review(Input):
    hash: str = Field(pattern=r'^[a-f0-9]{64}$')
    decision: Literal['approve', 'reject']


class Extract(Input):
    section_keys: list[str] = Field(default_factory=list, max_length=10)
    query: str = Field(default='', max_length=500)
    max_chars: int = Field(default=8000, ge=1, le=12000)
