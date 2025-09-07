import requests
import json
import datetime
import uuid
from typing import Dict, Any, Optional, List, Union

# Import the base client to extend it
from onelink_base_client import OneLinkBaseClient


class OneLinkAdvancedClient(OneLinkBaseClient):
    """
    Advanced client for 1Link API integration, extending the base client with:
    - Account Title Fetching
    - Alias Inquiry
    """
    
    def __init__(
        self, 
        client_id: str,
        client_secret: str,
        is_production: bool = False
    ):
        """
        Initialize the 1Link Advanced API client.
        
        Args:
            client_id: The X-IBM-Client-Id for API authentication
            client_secret: The client secret for OAuth authentication
            is_production: Flag to determine whether to use production or sandbox environment
        """
        # Initialize the base client
        super().__init__(client_id, client_secret, is_production)
        
        # Account Title Fetch endpoints
        self.pre_rtp_title_fetch_url = f"{self.base_url}/1Link/preRTPTitleFetch"
        self.pre_rtp_title_fetch_merchant_url = f"{self.base_url}/1Link/preRTPTitleFetchMerchant"
        self.pre_rtp_title_fetch_aggregator_url = f"{self.base_url}/1Link/preRTPTitleFetchAggregator"
        
        # Alias Inquiry endpoints
        self.pre_rtp_alias_inquiry_url = f"{self.base_url}/1Link/preRTPAliasInquiry"
        self.pre_rtp_alias_inquiry_merchant_url = f"{self.base_url}/1Link/preRTPAliasInquiryMerchant"
        self.pre_rtp_alias_inquiry_aggregator_url = f"{self.base_url}/1Link/preRTPAliasInquiryAggregator"
    
    # =====================================================================
    # Account Title Fetch Methods
    # =====================================================================
    
    def fetch_account_title(
        self,
        member_id: str,
        iban: str,
        rrn: str,
        stan: str
    ) -> Dict[str, Any]:
        """
        Fetch account title and type information before making an RTP request.
        
        Args:
            member_id: The member institution ID
            iban: International Bank Account Number of the target account
            rrn: Retrieval Reference Number
            stan: System Trace Audit Number
            
        Returns:
            Dict[str, Any]: The API response with account title and type information
        """
        # Prepare request payload
        payload = {
            "customerDetails": {
                "memberid": member_id,
                "iban": iban
            },
            "info": {
                "rrn": rrn,
                "stan": stan
            }
        }
        
        return self._make_api_request(self.pre_rtp_title_fetch_url, payload)
    
    def fetch_account_title_merchant(
        self,
        merchant_details: Dict[str, Any],
        payer_details: Dict[str, Any],
        customer_details: Dict[str, Any],
        contact_details: Dict[str, Any],
        rrn: str,
        stan: str
    ) -> Dict[str, Any]:
        """
        Fetch account title and type information for a merchant before making an RTP request.
        
        Args:
            merchant_details: Dictionary containing merchant information
            payer_details: Dictionary containing payer information
            customer_details: Dictionary containing customer information including memberid and iban
            contact_details: Dictionary containing contact information
            rrn: Retrieval Reference Number
            stan: System Trace Audit Number
            
        Returns:
            Dict[str, Any]: The API response with account title and type information
        """
        # Prepare request payload
        payload = {
            "merchantDetails": merchant_details,
            "payerDetails": payer_details,
            "customerDetails": customer_details,
            "contactDetails": contact_details,
            "info": {
                "rrn": rrn,
                "stan": stan
            }
        }
        
        return self._make_api_request(self.pre_rtp_title_fetch_merchant_url, payload)
    
    def fetch_account_title_aggregator(
        self,
        merchant_details: Dict[str, Any],
        customer_details: Dict[str, Any],
        rrn: str,
        stan: str
    ) -> Dict[str, Any]:
        """
        Fetch account title and type information for an aggregator before making an RTP request.
        
        Args:
            merchant_details: Dictionary containing merchant information (merchantID, subDept)
            customer_details: Dictionary containing customer information including memberid and iban
            rrn: Retrieval Reference Number
            stan: System Trace Audit Number
            
        Returns:
            Dict[str, Any]: The API response with account title and type information
        """
        # Prepare request payload
        payload = {
            "merchantDetails": merchant_details,
            "customerDetails": customer_details,
            "info": {
                "rrn": rrn,
                "stan": stan
            }
        }
        
        return self._make_api_request(self.pre_rtp_title_fetch_aggregator_url, payload)
    
    # =====================================================================
    # Alias Inquiry Methods
    # =====================================================================
    
    def perform_alias_inquiry(
        self,
        alias_type: str,
        alias_value: str,
        rrn: str,
        stan: str
    ) -> Dict[str, Any]:
        """
        Fetch customer account details via ALIAS.
        
        Args:
            alias_type: The type of alias (e.g., phone number, email)
            alias_value: The value of the alias
            rrn: Retrieval Reference Number
            stan: System Trace Audit Number
            
        Returns:
            Dict[str, Any]: The API response with account details
        """
        # Prepare request payload
        payload = {
            "alias": {
                "type": alias_type,
                "value": alias_value
            },
            "info": {
                "rrn": rrn,
                "stan": stan
            }
        }
        
        return self._make_api_request(self.pre_rtp_alias_inquiry_url, payload)
    
    def perform_alias_inquiry_merchant(
        self,
        merchant_details: Dict[str, Any],
        contact_details: Dict[str, Any],
        alias_type: str,
        alias_value: str,
        rrn: str,
        stan: str
    ) -> Dict[str, Any]:
        """
        Fetch customer account details via ALIAS for a merchant.
        
        Args:
            merchant_details: Dictionary containing merchant information
            contact_details: Dictionary containing contact information
            alias_type: The type of alias (e.g., phone number, email)
            alias_value: The value of the alias
            rrn: Retrieval Reference Number
            stan: System Trace Audit Number
            
        Returns:
            Dict[str, Any]: The API response with account details
        """
        # Prepare request payload
        payload = {
            "merchantDetails": merchant_details,
            "contactDetails": contact_details,
            "alias": {
                "type": alias_type,
                "value": alias_value
            },
            "info": {
                "rrn": rrn,
                "stan": stan
            }
        }
        
        return self._make_api_request(self.pre_rtp_alias_inquiry_merchant_url, payload)
    
    def perform_alias_inquiry_aggregator(
        self,
        merchant_details: Dict[str, Any],
        alias_type: str,
        alias_value: str,
        rrn: str,
        stan: str
    ) -> Dict[str, Any]:
        """
        Fetch customer account details via ALIAS for an aggregator.
        
        Args:
            merchant_details: Dictionary containing merchant information (merchantID, subDept)
            alias_type: The type of alias (e.g., phone number, email)
            alias_value: The value of the alias
            rrn: Retrieval Reference Number
            stan: System Trace Audit Number
            
        Returns:
            Dict[str, Any]: The API response with account details
        """
        # Prepare request payload
        payload = {
            "alias": {
                "type": alias_type,
                "value": alias_value
            },
            "info": {
                "rrn": rrn,
                "stan": stan
            },
            "merchantDetails": merchant_details
        }
        
        return self._make_api_request(self.pre_rtp_alias_inquiry_aggregator_url, payload)


# =====================================================================
# Usage Examples
# =====================================================================

def example_account_title_fetch():
    """Examples of account title fetch operations"""
    # Initialize the client
    client = OneLinkAdvancedClient(
        client_id="your_client_id_here",
        client_secret="your_client_secret_here",
        is_production=False
    )
    
    # Example 1: Basic account title fetch
    try:
        response = client.fetch_account_title(
            member_id="4536568956059648",
            iban="DE89 3704 0044 0532 0130 00",
            rrn="enucejopnakk",
            stan="towuca"
        )
        
        print("Account title fetch completed")
        print(f"Response code: {response.get('responseCode')}")
        print(f"Description: {response.get('responseDescription')}")
        
    except Exception as e:
        print(f"Error fetching account title: {str(e)}")
    
    # Example 2: Merchant account title fetch
    try:
        merchant_details = {
            "dbaName": "SOME DBA NAME",
            "merchantName": "MERCHANT ACCOUNT TITLE",
            "merchantCategoryCode": "5411",
            "merchantID": "70425271300379",
            "postalAddress": {
                "townName": "KARACHI",
                "subDept": "3791001",
                "addressLine": "Free Format Address"
            }
        }
        
        payer_details = {
            "additionalRequiredDetails": "tiz",
            "identificationDetails": {
                "loyaltyNo": "jebmilujacibivus",
                "customerLabel": "hefafupokebueri"
            }
        }
        
        customer_details = {
            "memberid": "2958121246916608",
            "iban": "DE89 3704 0044 0532 0130 00"
        }
        
        contact_details = {
            "phoneNo": "+92-3055520420",
            "mobileNo": "+92-3055520419",
            "email": "payee@karachi.pk",
            "dept": "SOME BRANCH",
            "website": "www.merchant.pk",
            "merchantChannelId": "400"
        }
        
        response = client.fetch_account_title_merchant(
            merchant_details=merchant_details,
            payer_details=payer_details,
            customer_details=customer_details,
            contact_details=contact_details,
            rrn="hohafogfolet",
            stan="rishud"
        )
        
        print("\nMerchant account title fetch completed")
        print(f"Response code: {response.get('responseCode')}")
        print(f"Description: {response.get('responseDescription')}")
        
    except Exception as e:
        print(f"Error fetching merchant account title: {str(e)}")
    
    # Example 3: Aggregator account title fetch
    try:
        merchant_details = {
            "merchantID": "4650194769543168",
            "subDept": "naklotwe"
        }
        
        customer_details = {
            "memberid": "2156472291033088",
            "iban": "DE89 3704 0044 0532 0130 00"
        }
        
        response = client.fetch_account_title_aggregator(
            merchant_details=merchant_details,
            customer_details=customer_details,
            rrn="pafgedganuir",
            stan="pozema"
        )
        
        print("\nAggregator account title fetch completed")
        print(f"Response code: {response.get('responseCode')}")
        print(f"Description: {response.get('responseDescription')}")
        
    except Exception as e:
        print(f"Error fetching aggregator account title: {str(e)}")


def example_alias_inquiry():
    """Examples of alias inquiry operations"""
    # Initialize the client
    client = OneLinkAdvancedClient(
        client_id="your_client_id_here",
        client_secret="your_client_secret_here",
        is_production=False
    )
    
    # Example 1: Basic alias inquiry
    try:
        response = client.perform_alias_inquiry(
            alias_type="fetbueneju",
            alias_value="22.94",
            rrn="mowaniddapsu",
            stan="mojzuf"
        )
        
        print("Alias inquiry completed")
        print(f"Response code: {response.get('responseCode')}")
        print(f"Description: {response.get('responseDescription')}")
        
    except Exception as e:
        print(f"Error performing alias inquiry: {str(e)}")
    
    # Example 2: Merchant alias inquiry
    try:
        merchant_details = {
            "dbaName": "SOME DBA NAME",
            "merchantName": "MERCHANT ACCOUNT TITLE",
            "merchantCategoryCode": "5411",
            "merchantID": "70425271300379",
            "postalAddress": {
                "townName": "KARACHI",
                "subDept": "3791001",
                "addressLine": "Free Format Address"
            }
        }
        
        contact_details = {
            "phoneNo": "+92-3055520420",
            "mobileNo": "+92-3055520419",
            "email": "payee@karachi.pk",
            "dept": "SOME BRANCH",
            "website": "www.merchant.pk",
            "merchantChannelId": "400"
        }
        
        response = client.perform_alias_inquiry_merchant(
            merchant_details=merchant_details,
            contact_details=contact_details,
            alias_type="madpovdecu",
            alias_value="38.73",
            rrn="jiduvapefadt",
            stan="filtua"
        )
        
        print("\nMerchant alias inquiry completed")
        print(f"Response code: {response.get('responseCode')}")
        print(f"Description: {response.get('responseDescription')}")
        
    except Exception as e:
        print(f"Error performing merchant alias inquiry: {str(e)}")
    
    # Example 3: Aggregator alias inquiry
    try:
        merchant_details = {
            "merchantID": "3061561881001984",
            "subDept": "ikuifbec"
        }
        
        response = client.perform_alias_inquiry_aggregator(
            merchant_details=merchant_details,
            alias_type="kihufanell",
            alias_value="97.25",
            rrn="cewrukcuebiz",
            stan="golios"
        )
        
        print("\nAggregator alias inquiry completed")
        print(f"Response code: {response.get('responseCode')}")
        print(f"Description: {response.get('responseDescription')}")
        
    except Exception as e:
        print(f"Error performing aggregator alias inquiry: {str(e)}")


if __name__ == "__main__":
    print("=== Account Title Fetch Examples ===")
    example_account_title_fetch()
    
    print("\n=== Alias Inquiry Examples ===")
    example_alias_inquiry()