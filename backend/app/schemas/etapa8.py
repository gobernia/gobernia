from pydantic import BaseModel, Field, field_validator, model_validator

VALID_AGENTS = {"CFO", "CSO", "CRO", "Auditor"}

VALID_TONES = {
    "formal":        "Formal y técnico — reportes estructurados con datos precisos",
    "strategic":     "Estratégico — visión de largo plazo y análisis de tendencias",
    "direct":        "Directo — al punto, sin rodeos, alertas claras",
    "collaborative": "Colaborativo — propuestas con alternativas y consenso",
}

VALID_SENSITIVITIES = {
    "high":   "Alta — alerta ante cualquier desviación del benchmark",
    "medium": "Media — solo umbrales críticos definidos en el spec",
    "low":    "Baja — únicamente situaciones de riesgo severo",
}

VALID_FREQUENCIES = {
    "monthly":    "Mensual (12 sesiones/año)",
    "bimonthly":  "Bimestral (6 sesiones/año)",
    "quarterly":  "Trimestral (4 sesiones/año)",
    "semiannual": "Semestral (2 sesiones/año)",
}


class AgentConfig(BaseModel):
    agent: str
    tone: str
    alert_sensitivity: str
    custom_instructions: str | None = Field(default=None, max_length=500)

    @field_validator("agent")
    @classmethod
    def agent_valido(cls, v: str) -> str:
        if v not in VALID_AGENTS:
            raise ValueError(f"Agente '{v}' no válido. Opciones: {', '.join(VALID_AGENTS)}")
        return v

    @field_validator("tone")
    @classmethod
    def tone_valido(cls, v: str) -> str:
        if v not in VALID_TONES:
            raise ValueError(f"Tono '{v}' no válido. Opciones: {', '.join(VALID_TONES)}")
        return v

    @field_validator("alert_sensitivity")
    @classmethod
    def sensitivity_valida(cls, v: str) -> str:
        if v not in VALID_SENSITIVITIES:
            raise ValueError(f"Sensibilidad '{v}' no válida.")
        return v


class BoardExpectations(BaseModel):
    session_frequency: str
    priority_topics: list[str] = Field(min_length=1, max_length=5)
    success_definition: str = Field(min_length=10, max_length=400)

    @field_validator("session_frequency")
    @classmethod
    def frequency_valida(cls, v: str) -> str:
        if v not in VALID_FREQUENCIES:
            raise ValueError(f"Frecuencia '{v}' no válida.")
        return v

    @field_validator("priority_topics")
    @classmethod
    def topics_no_vacios(cls, v: list[str]) -> list[str]:
        cleaned = [t.strip() for t in v if t.strip()]
        if not cleaned:
            raise ValueError("priority_topics no puede estar vacío.")
        return cleaned


class Etapa8Input(BaseModel):
    vision_statement: str = Field(min_length=20, max_length=500)
    main_goals: list[str] = Field(min_length=1, max_length=5)
    board_expectations: BoardExpectations
    agent_configs: list[AgentConfig] = Field(min_length=1)

    @field_validator("main_goals")
    @classmethod
    def goals_no_vacios(cls, v: list[str]) -> list[str]:
        cleaned = [g.strip() for g in v if g.strip()]
        if not cleaned:
            raise ValueError("main_goals no puede estar vacío.")
        return cleaned

    @model_validator(mode="after")
    def todos_los_agentes_configurados(self) -> "Etapa8Input":
        configured = {c.agent for c in self.agent_configs}
        missing = VALID_AGENTS - configured
        if missing:
            raise ValueError(f"Faltan configuraciones para: {', '.join(sorted(missing))}")
        duplicates = [a for a in configured if sum(1 for c in self.agent_configs if c.agent == a) > 1]
        if duplicates:
            raise ValueError(f"Agentes duplicados: {', '.join(duplicates)}")
        return self


class AgentConfigSummary(BaseModel):
    agent: str
    tone: str
    tone_label: str
    alert_sensitivity: str
    sensitivity_label: str
    custom_instructions: str | None


class Etapa8ConfigOptions(BaseModel):
    agents: list[str]
    tones: dict[str, str]
    sensitivities: dict[str, str]
    frequencies: dict[str, str]


class Etapa8Output(BaseModel):
    session_id: str
    completed_stages: list[int]
    vision_statement: str
    main_goals: list[str]
    agent_configs: list[AgentConfigSummary]
    session_frequency: str
    next_stage: int
