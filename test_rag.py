#!/usr/bin/env python3
"""
Comprehensive Test Suite for Multi-Tenant RAG Agent
Tests all components: TenantConfig, ClientFactory, ProductSearch, and RAG Agent
"""

import asyncio
import sys
import time
import json
from typing import Dict, Any, List
import httpx
from datetime import datetime

# Add project root to path
sys.path.insert(0, '/home/ec2-user/retail-ai')

from core.models.tenant import TenantConfiguration, TenantPineconeConfig, TenantSupabaseConfig
from core.services.tenant_config import TenantConfigManager
from core.services.client_factory import TenantClientFactory
from core.services.product_search import MultiTenantProductSearch
from core.database.redis_client import RedisClient

class RAGTestSuite:
    """Comprehensive RAG Agent Test Suite"""
    
    def __init__(self):
        self.redis_client = None
        self.config_manager = None
        self.client_factory = None
        self.product_search = None
        self.test_results = {}
        
    async def run_all_tests(self):
        """Run all RAG agent tests"""
        
        print("🧪 MULTI-TENANT RAG AGENT - COMPREHENSIVE TEST SUITE")
        print("=" * 70)
        
        try:
            # Initialize components
            await self._initialize_components()
            
            # Run test categories
            await self._test_tenant_configuration()
            await self._test_client_factory()
            await self._test_product_search_engine()
            await self._test_rag_agent_service()
            await self._test_integration_scenarios()
            
            # Summary
            self._print_test_summary()
            
        except Exception as e:
            print(f"❌ Test suite failed during initialization: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await self._cleanup()
    
    async def _initialize_components(self):
        """Initialize test components"""
        print("\n🔧 Initializing Test Components...")
        
        try:
            # Redis connection
            self.redis_client = RedisClient()
            await self.redis_client.connect()
            print("✅ Redis connected")
            
            # Core components
            self.config_manager = TenantConfigManager(self.redis_client)
            self.client_factory = TenantClientFactory()
            self.product_search = MultiTenantProductSearch(self.config_manager, self.client_factory)
            
            print("✅ Components initialized")
            
        except Exception as e:
            print(f"❌ Component initialization failed: {e}")
            raise
    
    async def _test_tenant_configuration(self):
        """Test tenant configuration management"""
        print("\n📋 Testing Tenant Configuration Management...")
        
        test_name = "tenant_configuration"
        self.test_results[test_name] = {"passed": 0, "failed": 0, "details": []}
        
        # Test 1: Load existing tenant config
        try:
            config = await self.config_manager.get_tenant_config("test_retailer")
            assert config is not None, "Config should not be None"
            assert config.tenant_id == "test_retailer", "Tenant ID should match"
            assert isinstance(config, TenantConfiguration), "Should return TenantConfiguration instance"
            
            self._log_test_result(test_name, "Load existing tenant config", True)
            
        except Exception as e:
            self._log_test_result(test_name, "Load existing tenant config", False, str(e))
        
        # Test 2: Load non-existent tenant
        try:
            config = await self.config_manager.get_tenant_config("non_existent_tenant")
            assert config is None, "Non-existent tenant should return None"
            
            self._log_test_result(test_name, "Load non-existent tenant", True)
            
        except Exception as e:
            self._log_test_result(test_name, "Load non-existent tenant", False, str(e))
        
        # Test 3: List available tenants
        try:
            tenants = await self.config_manager.list_tenants()
            assert len(tenants) >= 3, "Should have at least 3 sample tenants"
            assert "test_retailer" in tenants, "Should include test_retailer"
            
            self._log_test_result(test_name, "List available tenants", True)
            
        except Exception as e:
            self._log_test_result(test_name, "List available tenants", False, str(e))
        
        # Test 4: Validate tenant configuration structure
        try:
            config = await self.config_manager.get_tenant_config("fashion_retailer")
            
            # Check required fields
            assert hasattr(config, 'pinecone'), "Should have pinecone config"
            assert hasattr(config, 'supabase'), "Should have supabase config"
            assert hasattr(config, 'product_schema'), "Should have product schema"
            
            # Check methods
            search_fields = config.get_search_fields()
            assert len(search_fields) > 0, "Should have searchable fields"
            
            filterable_fields = config.get_filterable_fields()
            assert len(filterable_fields) > 0, "Should have filterable fields"
            
            self._log_test_result(test_name, "Validate configuration structure", True)
            
        except Exception as e:
            self._log_test_result(test_name, "Validate configuration structure", False, str(e))
    
    async def _test_client_factory(self):
        """Test client factory functionality"""
        print("\n🏭 Testing Client Factory...")
        
        test_name = "client_factory"
        self.test_results[test_name] = {"passed": 0, "failed": 0, "details": []}
        
        # Test 1: Create clients for valid tenant
        try:
            config = await self.config_manager.get_tenant_config("test_retailer")
            pinecone_client, supabase_client, embedding_model = await self.client_factory.get_tenant_clients(config)
            
            assert pinecone_client is not None, "Pinecone client should be created"
            assert supabase_client is not None, "Supabase client should be created"
            assert embedding_model is not None, "Embedding model should be loaded"
            
            # Test embedding model
            test_embeddings = embedding_model.encode(["test query"])
            assert len(test_embeddings) > 0, "Should generate embeddings"
            assert len(test_embeddings[0]) > 0, "Embeddings should have dimensions"
            
            self._log_test_result(test_name, "Create clients for valid tenant", True)
            
        except Exception as e:
            self._log_test_result(test_name, "Create clients for valid tenant", False, str(e))
        
        # Test 2: Test client caching
        try:
            config = await self.config_manager.get_tenant_config("test_retailer")
            
            # Get clients twice
            clients1 = await self.client_factory.get_tenant_clients(config)
            clients2 = await self.client_factory.get_tenant_clients(config)
            
            # Should return same instances (cached)
            assert clients1[0] is clients2[0], "Pinecone client should be cached"
            assert clients1[1] is clients2[1], "Supabase client should be cached"
            
            self._log_test_result(test_name, "Test client caching", True)
            
        except Exception as e:
            self._log_test_result(test_name, "Test client caching", False, str(e))
        
        # Test 3: Multiple tenant isolation
        try:
            config1 = await self.config_manager.get_tenant_config("test_retailer")
            config2 = await self.config_manager.get_tenant_config("fashion_retailer")
            
            clients1 = await self.client_factory.get_tenant_clients(config1)
            clients2 = await self.client_factory.get_tenant_clients(config2)
            
            # Different tenants should have different client instances
            assert clients1[0] is not clients2[0], "Different tenants should have isolated Pinecone clients"
            assert clients1[1] is not clients2[1], "Different tenants should have isolated Supabase clients"
            
            self._log_test_result(test_name, "Multiple tenant isolation", True)
            
        except Exception as e:
            self._log_test_result(test_name, "Multiple tenant isolation", False, str(e))
    
    async def _test_product_search_engine(self):
        """Test the RAG product search engine"""
        print("\n🔍 Testing RAG Product Search Engine...")
        
        test_name = "product_search_engine"
        self.test_results[test_name] = {"passed": 0, "failed": 0, "details": []}
        
        # Test 1: Basic product search
        try:
            search_entity = {
                "query": "running shoes",
                "category": "shoes",
                "brand": "nike"
            }
            
            result = await self.product_search.search_products("test_retailer", search_entity)
            
            assert "products" in result, "Result should contain products"
            assert "total" in result, "Result should contain total count"
            assert "tenant_id" in result, "Result should contain tenant_id"
            assert "rag_response" in result, "Result should contain LLM-generated response"
            assert result["tenant_id"] == "test_retailer", "Tenant ID should match"
            
            self._log_test_result(test_name, "Basic product search", True, 
                               f"Found {result['total']} products with RAG response")
            
        except Exception as e:
            self._log_test_result(test_name, "Basic product search", False, str(e))
        
        # Test 2: Search with filters
        try:
            search_entity = {
                "query": "shoes",
                "brand": "nike",
                "color": "red",
                "max_price": 150
            }
            
            result = await self.product_search.search_products("test_retailer", search_entity)
            
            # Validate filtering
            for product in result.get("products", []):
                if "brand" in product:
                    assert "nike" in product["brand"].lower(), "Brand filter should be applied"
                if "price" in product and product["price"]:
                    assert product["price"] <= 150, "Price filter should be applied"
            
            self._log_test_result(test_name, "Search with filters", True,
                               f"Filters applied correctly, found {result['total']} products")
            
        except Exception as e:
            self._log_test_result(test_name, "Search with filters", False, str(e))
        
        # Test 3: Empty query handling
        try:
            search_entity = {"query": ""}
            result = await self.product_search.search_products("test_retailer", search_entity)
            
            assert result["total"] == 0, "Empty query should return no results"
            assert "rag_response" in result, "Should still have RAG response"
            
            self._log_test_result(test_name, "Empty query handling", True)
            
        except Exception as e:
            self._log_test_result(test_name, "Empty query handling", False, str(e))
        
        # Test 4: Invalid tenant handling
        try:
            search_entity = {"query": "test"}
            result = await self.product_search.search_products("invalid_tenant", search_entity)
            
            assert "error" in result, "Invalid tenant should return error"
            
            self._log_test_result(test_name, "Invalid tenant handling", True)
            
        except Exception as e:
            self._log_test_result(test_name, "Invalid tenant handling", False, str(e))
        
        # Test 5: RAG response quality
        try:
            search_entity = {
                "query": "comfortable running shoes for daily jogging",
                "max_price": 200
            }
            
            result = await self.product_search.search_products("test_retailer", search_entity)
            rag_response = result.get("rag_response", "")
            
            assert len(rag_response) > 100, "RAG response should be substantial"
            assert any(keyword in rag_response.lower() for keyword in ["running", "shoes", "comfortable"]), \
                   "RAG response should be relevant to search"
            
            self._log_test_result(test_name, "RAG response quality", True,
                               f"Generated {len(rag_response)} character response")
            
        except Exception as e:
            self._log_test_result(test_name, "RAG response quality", False, str(e))
    
    async def _test_rag_agent_service(self):
        """Test the RAG agent HTTP service"""
        print("\n🌐 Testing RAG Agent HTTP Service...")
        
        test_name = "rag_agent_service"
        self.test_results[test_name] = {"passed": 0, "failed": 0, "details": []}
        
        # Check if RAG agent is running
        rag_agent_url = "http://localhost:8003"
        
        # Test 1: Health check
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{rag_agent_url}/health", timeout=5.0)
                
                if response.status_code == 200:
                    health_data = response.json()
                    assert health_data["service"] == "rag-agent", "Service should be rag-agent"
                    
                    self._log_test_result(test_name, "Health check", True, 
                                       f"Status: {health_data['status']}")
                else:
                    raise Exception(f"Health check failed with status {response.status_code}")
                    
        except httpx.ConnectError:
            self._log_test_result(test_name, "Health check", False, 
                               "RAG agent not running on port 8003")
            return  # Skip remaining HTTP tests if service is down
        except Exception as e:
            self._log_test_result(test_name, "Health check", False, str(e))
        
        # Test 2: Search endpoint
        try:
            search_request = {
                "tenant_id": "test_retailer",
                "search_entity": {
                    "query": "running shoes",
                    "brand": "nike"
                },
                "max_results": 10
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{rag_agent_url}/search",
                    json=search_request,
                    timeout=30.0
                )
                
                assert response.status_code == 200, f"Search should return 200, got {response.status_code}"
                
                result = response.json()
                assert result["success"] == True, "Search should be successful"
                assert "rag_response" in result, "Should contain RAG response"
                assert result["tenant_id"] == "test_retailer", "Tenant ID should match"
                
                self._log_test_result(test_name, "Search endpoint", True,
                                   f"Found {result['total_results']} products")
                
        except Exception as e:
            self._log_test_result(test_name, "Search endpoint", False, str(e))
        
        # Test 3: List tenants endpoint
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{rag_agent_url}/tenants", timeout=5.0)
                
                assert response.status_code == 200, "Tenants endpoint should return 200"
                
                result = response.json()
                assert "tenants" in result, "Should contain tenants list"
                assert len(result["tenants"]) >= 3, "Should have sample tenants"
                
                self._log_test_result(test_name, "List tenants endpoint", True,
                                   f"Found {len(result['tenants'])} tenants")
                
        except Exception as e:
            self._log_test_result(test_name, "List tenants endpoint", False, str(e))
        
        # Test 4: Tenant config endpoint
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{rag_agent_url}/tenants/test_retailer/config", timeout=5.0)
                
                assert response.status_code == 200, "Config endpoint should return 200"
                
                config = response.json()
                assert config["tenant_id"] == "test_retailer", "Tenant ID should match"
                assert "embedding_model" in config, "Should contain embedding model info"
                assert "filter_options" in config, "Should contain filter options"
                
                self._log_test_result(test_name, "Tenant config endpoint", True)
                
        except Exception as e:
            self._log_test_result(test_name, "Tenant config endpoint", False, str(e))
    
    async def _test_integration_scenarios(self):
        """Test realistic integration scenarios"""
        print("\n🔄 Testing Integration Scenarios...")
        
        test_name = "integration_scenarios"
        self.test_results[test_name] = {"passed": 0, "failed": 0, "details": []}
        
        # Scenario 1: Complete shopping journey
        try:
            # Simulate a customer journey with accumulated search entity
            searches = [
                {"query": "shoes"},
                {"query": "running shoes", "brand": "nike"},
                {"query": "red nike running shoes", "color": "red"},
                {"query": "red nike running shoes under $150", "max_price": 150}
            ]
            
            results = []
            for i, search_entity in enumerate(searches):
                result = await self.product_search.search_products("test_retailer", search_entity)
                results.append(result)
            
            # Validate journey progression
            assert all(r.get("total", 0) >= 0 for r in results), "All searches should complete"
            
            # Last search should be most specific
            final_result = results[-1]
            assert "nike" in final_result["rag_response"].lower(), "Final response should mention Nike"
            assert "red" in final_result["rag_response"].lower() or "$150" in final_result["rag_response"], \
                   "Final response should reference specific criteria"
            
            self._log_test_result(test_name, "Complete shopping journey", True,
                               f"Journey completed with {len(results)} searches")
            
        except Exception as e:
            self._log_test_result(test_name, "Complete shopping journey", False, str(e))
        
        # Scenario 2: Multi-tenant comparison
        try:
            search_entity = {"query": "shoes", "brand": "nike"}
            
            # Search across different tenants
            tenant_results = {}
            for tenant in ["test_retailer", "fashion_retailer", "electronics_store"]:
                result = await self.product_search.search_products(tenant, search_entity)
                tenant_results[tenant] = result
            
            # All tenants should handle the request
            assert all(r.get("tenant_id") == tenant for tenant, r in tenant_results.items()), \
                   "Each result should have correct tenant ID"
            
            self._log_test_result(test_name, "Multi-tenant comparison", True,
                               f"Tested {len(tenant_results)} tenants")
            
        except Exception as e:
            self._log_test_result(test_name, "Multi-tenant comparison", False, str(e))
        
        # Scenario 3: Performance test
        try:
            start_time = time.time()
            
            # Concurrent searches
            tasks = []
            for i in range(5):
                search_entity = {"query": f"test query {i}"}
                task = self.product_search.search_products("test_retailer", search_entity)
                tasks.append(task)
            
            results = await asyncio.gather(*tasks)
            
            total_time = time.time() - start_time
            avg_time = total_time / len(results)
            
            assert all(r.get("total", 0) >= 0 for r in results), "All searches should complete"
            assert avg_time < 5.0, "Average search time should be under 5 seconds"
            
            self._log_test_result(test_name, "Performance test", True,
                               f"Avg time: {avg_time:.2f}s for {len(results)} searches")
            
        except Exception as e:
            self._log_test_result(test_name, "Performance test", False, str(e))
    
    def _log_test_result(self, test_category: str, test_name: str, passed: bool, details: str = ""):
        """Log individual test result"""
        status = "✅" if passed else "❌"
        result_text = f"  {status} {test_name}"
        
        if details:
            result_text += f" - {details}"
        
        print(result_text)
        
        # Update results
        if passed:
            self.test_results[test_category]["passed"] += 1
        else:
            self.test_results[test_category]["failed"] += 1
        
        self.test_results[test_category]["details"].append({
            "test": test_name,
            "passed": passed,
            "details": details
        })
    
    def _print_test_summary(self):
        """Print comprehensive test summary"""
        print("\n" + "=" * 70)
        print("📊 TEST RESULTS SUMMARY")
        print("=" * 70)
        
        total_passed = 0
        total_failed = 0
        
        for category, results in self.test_results.items():
            passed = results["passed"]
            failed = results["failed"]
            total = passed + failed
            
            total_passed += passed
            total_failed += failed
            
            status_icon = "✅" if failed == 0 else "⚠️" if passed > failed else "❌"
            
            print(f"{status_icon} {category.replace('_', ' ').title()}: {passed}/{total} passed")
            
            # Show failed tests
            if failed > 0:
                for detail in results["details"]:
                    if not detail["passed"]:
                        print(f"    ❌ {detail['test']}: {detail['details']}")
        
        print("\n" + "-" * 70)
        
        overall_total = total_passed + total_failed
        success_rate = (total_passed / overall_total * 100) if overall_total > 0 else 0
        
        overall_status = "✅ PASSED" if total_failed == 0 else "⚠️ PARTIAL" if success_rate >= 70 else "❌ FAILED"
        
        print(f"🎯 OVERALL: {overall_status}")
        print(f"   Total Tests: {overall_total}")
        print(f"   Passed: {total_passed}")
        print(f"   Failed: {total_failed}")
        print(f"   Success Rate: {success_rate:.1f}%")
        
        if success_rate >= 90:
            print("\n🎉 Excellent! RAG agent is ready for production.")
        elif success_rate >= 70:
            print("\n👍 Good progress! Address failed tests before production.")
        else:
            print("\n⚠️  Significant issues found. Review failed tests carefully.")
    
    async def _cleanup(self):
        """Clean up test resources"""
        if self.redis_client:
            await self.redis_client.disconnect()
        print("\n🧹 Test cleanup completed")

async def main():
    """Run the comprehensive test suite"""
    test_suite = RAGTestSuite()
    await test_suite.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())