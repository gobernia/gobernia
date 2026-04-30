from enum import Enum


class IndustryType(str, Enum):
    manufacturing = "manufacturing"
    retail = "retail"
    professional_services = "professional_services"
    construction = "construction"
    food_beverage = "food_beverage"
    technology = "technology"
    health = "health"
    education = "education"
    transport_logistics = "transport_logistics"
    agro = "agro"
    other = "other"


class EmployeeRange(str, Enum):
    micro = "1-10"
    small = "11-50"
    medium = "51-200"
    large = "200+"


class RevenueRange(str, Enum):
    less_1m = "<1M"
    one_to_5m = "1M-5M"
    five_to_15m = "5M-15M"
    plus_15m = "15M+"


class BranchCount(str, Enum):
    single = "single"
    two_to_five = "2-5"
    six_plus = "6+"


class YearsOperating(str, Enum):
    startup = "0-3"
    growth = "4-10"
    mature = "10-25"
    veteran = "25+"


class FamilyGeneration(str, Enum):
    first = "1st"
    second = "2nd"
    third_plus = "3rd+"


class BoardStatus(str, Enum):
    yes = "yes"
    no = "no"
    in_progress = "in_progress"


class DirectiveRole(str, Enum):
    ceo = "ceo"
    cfo = "cfo"
    operations = "operations"
    commercial = "commercial"
    hr = "hr"
    shareholder = "shareholder"
    external_advisor = "external_advisor"
    other = "other"


class ChallengeType(str, Enum):
    commercial_growth = "commercial_growth"
    profitability = "profitability"
    talent = "talent"
    operations = "operations"
    organizational_clarity = "organizational_clarity"
    delegation_succession = "delegation_succession"
    market_position = "market_position"
    compliance_risk = "compliance_risk"
    innovation_technology = "innovation_technology"
    other = "other"


class AgentType(str, Enum):
    cfo = "CFO"
    cro = "CRO"
    cso = "CSO"
    auditor = "Auditor"


class FunctionalArea(str, Enum):
    finance = "finance"
    commercial = "commercial"
    operations = "operations"
    hr = "hr"
    strategy = "strategy"
    legal = "legal"
    family = "family"


class DiagnosticResponse(str, Enum):
    yes = "yes"
    partial = "partial"
    no = "no"
    unknown = "unknown"


class ProcessingStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    done = "done"
    error = "error"


class DocumentType(str, Enum):
    financial = "financial"
    strategic = "strategic"
    org_chart = "org_chart"
    other = "other"


class SessionFrequency(str, Enum):
    weekly = "weekly"
    biweekly = "biweekly"
    monthly = "monthly"


class AgentTone(str, Enum):
    direct = "direct"
    structured = "structured"
    balanced = "balanced"


class CentralizationLevel(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class GovernanceLevel(str, Enum):
    critical = "critical"
    developing = "developing"
    acceptable = "acceptable"
    solid = "solid"


class ExpectationType(str, Enum):
    truth_teller = "truth_teller"
    organizer = "organizer"
    decision_support = "decision_support"
    commitment_tracker = "commitment_tracker"
    benchmark = "benchmark"
