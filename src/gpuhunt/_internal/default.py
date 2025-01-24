import functools
import importlib
import logging
from typing import Callable, TypeVar

from typing_extensions import Concatenate, ParamSpec

from gpuhunt._internal.catalog import Catalog

logger = logging.getLogger(__name__)

ONLINE_PROVIDERS = ["cudo", "tensordock", "vastai", "vultr", "latitude", "crusoe", "genesiscloud", "leadergpu", "linode", "nebius", "scaleway", "seeweb"]


@functools.lru_cache
def default_catalog() -> Catalog:
    """
    Returns:
        the latest catalog with all available providers loaded
    """
    logger.info("Initializing default catalog...")
    catalog = Catalog()
    catalog.load()
    
    # Add all online providers
    provider_classes = {
        "tensordock": "TensorDockProvider",
        "vastai": "VastAIProvider",
        "vultr": "VultrProvider",
        "cudo": "CudoProvider",
        "latitude": "LatitudeProvider",
        "crusoe": "CrusoeProvider",
        "genesiscloud": "GenesisCloudProvider",
        "leadergpu": "LeaderGPUProvider",
        "linode": "LinodeProvider",
        "nebius": "NebiusProvider",
        "scaleway": "ScalewayProvider",
        "seeweb": "SeewebProvider"
    }
    
    for provider_name in ONLINE_PROVIDERS:
        module_name = f"gpuhunt.providers.{provider_name}"
        provider_class = provider_classes.get(provider_name)
        logger.info(f"Attempting to load provider: {provider_name} (class: {provider_class})")
        try:
            module = importlib.import_module(module_name)
            provider = getattr(module, provider_class)()
            # Special handling for providers that need configuration
            if provider_name == "nebius":
                logger.info("Skipping Nebius provider as it requires service account configuration")
                continue
            elif provider_name == "scaleway":
                logger.info("Skipping Scaleway provider due to OpenAI rate limits")
                continue
            catalog.add_provider(provider)
            logger.info(f"Successfully loaded provider: {provider_name}")
        except ImportError as e:
            logger.warning(f"Failed to import provider {provider_name}: {str(e)}")
        except AttributeError as e:
            logger.warning(f"Failed to initialize provider {provider_name}: {str(e)}")
        except Exception as e:
            logger.warning(f"Unexpected error loading provider {provider_name}: {str(e)}")
    
    return catalog


P = ParamSpec("P")
R = TypeVar("R")
Method = Callable[P, R]
CatalogMethod = Callable[Concatenate[Catalog, P], R]


def with_signature(method: CatalogMethod) -> Callable[[Method], Method]:
    """
    Returns:
        decorator to add the signature of the Catalog method to the decorated method
    """

    def decorator(func: Method) -> Method:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            return func(*args, **kwargs)

        return wrapper

    return decorator


@with_signature(Catalog.query)
def query(*args: P.args, **kwargs: P.kwargs) -> R:
    """
    Query the `default_catalog`.
    See `Catalog.query` for more details on parameters

    Returns:
        (List[CatalogItem]): the result of the query
    """
    return default_catalog().query(*args, **kwargs)
