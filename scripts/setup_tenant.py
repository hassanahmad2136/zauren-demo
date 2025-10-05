#!/usr/bin/env python3
"""
Setup script for creating a new tenant configuration.
"""

import asyncio
import argparse
from typing import Dict, Any

async def setup_tenant(tenant_id: str, config: Dict[str, Any] = None):
    """
    Set up a new retail tenant with default configuration.
    
    Args:
        tenant_id: Unique identifier for the tenant
        config: Optional tenant-specific configuration
    """
    print(f"Setting up tenant: {tenant_id}")
    
    default_config = {
        "name": tenant_id,
        "channels": ["whatsapp", "web"],
        "features": {
            "cart_enabled": True,
            "support_enabled": True,
            "product_search_enabled": True
        },
        "llm_config": {
            "model": "gpt-4",
            "max_tokens": 1000,
            "temperature": 0.7
        }
    }
    
    if config:
        default_config.update(config)
    
    # TODO: Save to database/config store
    print(f"Tenant {tenant_id} configured successfully!")
    print(f"Config: {default_config}")

def main():
    parser = argparse.ArgumentParser(description="Setup a new retail tenant")
    parser.add_argument("--tenant", required=True, help="Tenant ID")
    parser.add_argument("--name", help="Tenant display name")
    
    args = parser.parse_args()
    
    config = {}
    if args.name:
        config["name"] = args.name
    
    asyncio.run(setup_tenant(args.tenant, config))

if __name__ == "__main__":
    main()
