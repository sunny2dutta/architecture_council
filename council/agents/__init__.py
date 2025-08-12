from .systems import LLMSystemsGeneralist
from .infra import LLMInfraReliability
from .data_integration import LLMDataIntegration
from .security import LLMSecurityCompliance
from .frontend import LLMFrontendMobile
from .domain import LLMGameDomain
from .ml import LLMMLExpert

def create_default_agents(client):
    return [
        LLMSystemsGeneralist(client),
        LLMInfraReliability(client),
        LLMDataIntegration(client),
        LLMSecurityCompliance(client),
        LLMFrontendMobile(client),
        LLMGameDomain(client),
        LLMMLExpert(client),
    ]
