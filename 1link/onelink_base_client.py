import requests
import json
import datetime
import uuid
from typing import Dict, Any, Optional, List, Union


class OneLinkBaseClient:
    """
    Base client for 1Link API integration, supporting:
    - OAuth authentication
    - QR Code Generation (Merchant and Aggregator)
    - RTP (Request to Pay) Transaction Operations
    """
    
    def __init__(
        self, 
        client_id: str,
        client_secret: str,
        is_production: bool = False
    ):
        """
        Initialize the 1Link API client.
        
        Args:
            client_id: The X-IBM-Client-Id for API authentication
            client_secret: The client secret for OAuth authentication
            is_production: Flag to determine whether to use production or sandbox environment
        """
        self.client_id = client_id
        self.client_secret = client_secret
        
        # Set base URLs based on environment
        if is_production:
            self.base_url = "https://api.1link.net.pk"
        else:
            self.base_url = "https://sandboxapi.1link.net.pk/uat-1link/sandbox"
        
        # Token URL is the same for all endpoints
        self.token_url = f"{self.base_url}/oauth2/token"
        
        # QR Code Generation endpoints
        self.merchant_qrc_url = f"{self.base_url}/1Link/generateDQRCMerchant"
        self.aggregator_qrc_url = f"{self.base_url}/1Link/generateDQRCAggregator"
        
        # RTP Transaction endpoints
        self.rtp_cancellation_url = f"{self.base_url}/1Link/rtpCancellation"
        self.status_inquiry_url = f"{self.base_url}/1Link/statusInquiry"
        
        # RTP Now endpoints
        self.rtp_now_merchant_url = f"{self.base_url}/1Link/rtpNowMerchant"
        self.rtp_now_aggregator_url = f"{self.base_url}/1Link/rtpNowAggregator"
        
        # RTP Later endpoints
        self.rtp_later_merchant_url = f"{self.base_url}/1Link/rtpLaterMerchant"
        self.rtp_later_aggregator_url = f"{self.base_url}/1Link/rtpLaterAggregator"
        
        self.access_token = None
        self.token_expiry = None
    
    def _get_oauth_token(self) -> str:
        """
        Fetch OAuth2 token for API authentication.
        
        Returns:
            str: The access token
        """
        headers = {
            "X-IBM-Client-Id": self.client_id,
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json"
        }
        
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": "1LinkApi"
        }
        
        response = requests.post(
            self.token_url,
            headers=headers,
            data=data,
            timeout=10  # Add timeout for faster failover
        )
        
        if response.status_code != 200:
            raise Exception(f"Failed to get OAuth token: {response.text}")
        
        token_data = response.json()
        self.access_token = token_data["access_token"]
        
        # Set token expiry (typically OAuth tokens last for 1 hour)
        expires_in = token_data.get("expires_in", 3600)  # Default to 1 hour if not specified
        self.token_expiry = datetime.datetime.now() + datetime.timedelta(seconds=expires_in)
        
        return self.access_token
    
    def _ensure_valid_token(self) -> str:
        """
        Ensure we have a valid OAuth token, refreshing if necessary.
        
        Returns:
            str: The valid access token
        """
        # If we don't have a token or it's expired, get a new one
        if not self.access_token or (self.token_expiry and datetime.datetime.now() >= self.token_expiry):
            return self._get_oauth_token()
        
        return self.access_token
    
    def _make_api_request(self, url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make an API request to 1Link with appropriate authentication.
        
        Args:
            url: The API endpoint URL
            payload: The request payload
            
        Returns:
            Dict[str, Any]: The API response
        """
        # Get a valid token
        token = self._ensure_valid_token()
        
        # Prepare headers
        headers = {
            "X-IBM-Client-Id": self.client_id,
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # Make the API request
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=10  # Add timeout for faster failover
        )
        
        # Check for successful response
        if response.status_code != 200:
            raise Exception(f"API request failed: {response.status_code} - {response.text}")
        
        return response.json()
    
    # =====================================================================
    # QR Code Generation Methods
    # =====================================================================
    
    def generate_dynamic_qrc_merchant(
        self,
        merchant_details: Dict[str, Any],
        payer_details: Optional[Dict[str, Any]] = None,
        payment_details: Optional[Dict[str, Any]] = None,
        info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate a Dynamic QR Code for a merchant.
        
        Args:
            merchant_details: Dictionary containing merchant information
            payer_details: Dictionary containing payer information (optional)
            payment_details: Dictionary containing payment information (optional)
            info: Dictionary containing additional transaction information (optional)
            
        Returns:
            Dict[str, Any]: The API response with QRC information
        """
        # Prepare request payload
        payload = {
            "merchantDetails": merchant_details
        }
        
        # Add optional parameters if provided
        if payer_details:
            payload["payerDetails"] = payer_details
        
        if payment_details:
            payload["paymentDetails"] = payment_details
        
        if info:
            payload["info"] = info
        
        return self._make_api_request(self.merchant_qrc_url, payload)
    
    def generate_dynamic_qrc_aggregator(
        self,
        merchant_details: Dict[str, Any],
        contact_details: Dict[str, Any],
        geo_location: Dict[str, Any],
        payer_details: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate a Dynamic QR Code for an Aggregator.
        
        Args:
            merchant_details: Dictionary containing merchant information (subDept, merchantID)
            contact_details: Dictionary containing contact information (merchantChannelId)
            geo_location: Dictionary containing geographical location data (lat, long)
            payer_details: Dictionary containing complete payer information including payment details and info
            
        Returns:
            Dict[str, Any]: The API response with QRC information
        """
        # Prepare request payload - note the specific structure required for aggregator QRC
        payload = {
            "merchantDetails": merchant_details,
            "contactDetails": contact_details,
            "geoLocation": geo_location,
            "payerDetails": payer_details
        }
        
        return self._make_api_request(self.aggregator_qrc_url, payload)
    
    # For backward compatibility
    def generate_dynamic_qrc(
        self,
        merchant_details: Dict[str, Any],
        payer_details: Optional[Dict[str, Any]] = None,
        payment_details: Optional[Dict[str, Any]] = None,
        info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Legacy method that calls generate_dynamic_qrc_merchant.
        Maintained for backward compatibility.
        """
        return self.generate_dynamic_qrc_merchant(
            merchant_details=merchant_details,
            payer_details=payer_details,
            payment_details=payment_details,
            info=info
        )
    
    # =====================================================================
    # RTP Transaction Methods
    # =====================================================================
    
    def cancel_rtp_transaction(
        self,
        stan: str,
        rtp_id: str,
        merchant_id: str,
        sub_dept: str
    ) -> Dict[str, Any]:
        """
        Cancel a Request to Pay (RTP) transaction.
        
        Args:
            stan: System Trace Audit Number - a unique identifier for the transaction
            rtp_id: The Request to Pay transaction ID to be cancelled
            merchant_id: The ID of the merchant who initiated the transaction
            sub_dept: The sub-department identifier
            
        Returns:
            Dict[str, Any]: The API response with cancellation status
        """
        # Prepare request payload
        payload = {
            "info": {
                "stan": stan,
                "rtpId": rtp_id,
                "merchantID": merchant_id,
                "subDept": sub_dept
            }
        }
        
        return self._make_api_request(self.rtp_cancellation_url, payload)
    
    def check_transaction_status(
        self,
        stan: str,
        rtp_id: str,
        merchant_id: str,
        sub_dept: str
    ) -> Dict[str, Any]:
        """
        Check the status of a Request to Pay (RTP) transaction.
        
        Args:
            stan: System Trace Audit Number - a unique identifier for the transaction
            rtp_id: The Request to Pay transaction ID to check
            merchant_id: The ID of the merchant who initiated the transaction
            sub_dept: The sub-department identifier
            
        Returns:
            Dict[str, Any]: The API response with transaction status information
        """
        # Prepare request payload
        payload = {
            "info": {
                "stan": stan,
                "rtpId": rtp_id,
                "merchantID": merchant_id,
                "subDept": sub_dept
            }
        }
        
        return self._make_api_request(self.status_inquiry_url, payload)
    
    # =====================================================================
    # RTP Now and Later Methods
    # =====================================================================
    
    def generate_rtp_now_merchant(
        self,
        merchant_details: Dict[str, Any],
        payer_details: Dict[str, Any],
        payment_details: Dict[str, Any],
        info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate a Request to Pay (RTP) Now request for a merchant.
        
        Args:
            merchant_details: Dictionary containing complete merchant information
            payer_details: Dictionary containing payer information
            payment_details: Dictionary containing payment information including rtpId and billNo
            info: Dictionary containing transaction information (stan, rrn)
            
        Returns:
            Dict[str, Any]: The API response with RTP request status
        """
        # Prepare request payload
        payload = {
            "merchantDetails": merchant_details,
            "payerDetails": payer_details,
            "paymentDetails": payment_details,
            "info": info
        }
        
        return self._make_api_request(self.rtp_now_merchant_url, payload)
    
    def generate_rtp_now_aggregator(
        self,
        merchant_details: Dict[str, Any],
        contact_details: Dict[str, Any],
        geo_location: Dict[str, Any],
        payer_details: Dict[str, Any],
        payment_details: Dict[str, Any],
        info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate a Request to Pay (RTP) Now request for an aggregator.
        
        Args:
            merchant_details: Dictionary containing merchant information (merchantID, subDept)
            contact_details: Dictionary containing contact information (merchantChannelId)
            geo_location: Dictionary containing geographical location data (lat, long)
            payer_details: Dictionary containing payer identification information
            payment_details: Dictionary containing payment information
            info: Dictionary containing transaction information (stan, rrn)
            
        Returns:
            Dict[str, Any]: The API response with RTP request status
        """
        # Prepare request payload
        # Note: For aggregator endpoints, the payment_details and info are nested within payer_details
        payer_with_nested_details = payer_details.copy()
        payer_with_nested_details["paymentDetails"] = payment_details
        payer_with_nested_details["info"] = info
        
        payload = {
            "merchantDetails": merchant_details,
            "contactDetails": contact_details,
            "geoLocation": geo_location,
            "payerDetails": payer_with_nested_details
        }
        
        return self._make_api_request(self.rtp_now_aggregator_url, payload)
    
    def generate_rtp_later_merchant(
        self,
        merchant_details: Dict[str, Any],
        payer_details: Dict[str, Any],
        payment_details: Dict[str, Any],
        info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate a Request to Pay (RTP) Later request for a merchant.
        This is for scheduled or future-dated payments.
        
        Args:
            merchant_details: Dictionary containing complete merchant information
            payer_details: Dictionary containing payer information
            payment_details: Dictionary containing payment information including rtpId and billNo
            info: Dictionary containing transaction information (stan, rrn)
            
        Returns:
            Dict[str, Any]: The API response with RTP request status
        """
        # Prepare request payload
        payload = {
            "merchantDetails": merchant_details,
            "payerDetails": payer_details,
            "paymentDetails": payment_details,
            "info": info
        }
        
        return self._make_api_request(self.rtp_later_merchant_url, payload)
    
    def generate_rtp_later_aggregator(
        self,
        merchant_details: Dict[str, Any],
        contact_details: Dict[str, Any],
        geo_location: Dict[str, Any],
        payer_details: Dict[str, Any],
        payment_details: Dict[str, Any],
        info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate a Request to Pay (RTP) Later request for an aggregator.
        This is for scheduled or future-dated payments.
        
        Args:
            merchant_details: Dictionary containing merchant information (merchantID, subDept)
            contact_details: Dictionary containing contact information (merchantChannelId)
            geo_location: Dictionary containing geographical location data (lat, long)
            payer_details: Dictionary containing payer identification information
            payment_details: Dictionary containing payment information
            info: Dictionary containing transaction information (stan, rrn)
            
        Returns:
            Dict[str, Any]: The API response with RTP request status
        """
        # Prepare request payload
        # Note: For aggregator endpoints, the payment_details and info are nested within payer_details
        payer_with_nested_details = payer_details.copy()
        payer_with_nested_details["paymentDetails"] = payment_details
        payer_with_nested_details["info"] = info
        
        payload = {
            "merchantDetails": merchant_details,
            "contactDetails": contact_details,
            "geoLocation": geo_location,
            "payerDetails": payer_with_nested_details
        }
        
        return self._make_api_request(self.rtp_later_aggregator_url, payload)


# =====================================================================
# Usage Examples
# =====================================================================

def example_qrc_generation():
    """Examples of generating QR codes for merchant and aggregator"""
    # Initialize the client
    client = OneLinkBaseClient(
        client_id="your_client_id_here",
        client_secret="your_client_secret_here",
        is_production=False
    )
    
    # Example 1: Generate Merchant QR Code
    try:
        # Define merchant details
        merchant_details = {
            "dbaName": "SOME DBA NAME",
            "merchantName": "MERCHANT ACCOUNT TITLE",
            "iban": "PK81KHYB0022000001111111",
            "bankBic": "KHYB002",
            "merchantCategoryCode": "5411",
            "merchantID": "70425271300379",
            "postalAddress": {
                "townName": "Free Format Address",
                "addressLine": "Free Format Address",
                "subDept": "3791001"
            },
            "contactDetails": {
                "phoneNo": "+92-3055520420",
                "mobileNo": "+92-3055520419",
                "email": "payee@karachi.pk",
                "dept": "SOME BRANCH",
                "website": "www.merchant.pk",
                "merchantChannelId": "www.merchant.pk"
            },
            "geoLocation": {
                "lat": "24.875061",
                "long": "67.038332"
            }
        }
        
        # Define payer details
        payer_details = {
            "additionalRequiredDetails": "AME",
            "identificationDetails": {
                "loyaltyNo": "SOME LOYALTY NUMB",
                "customerLabel": "SOME CUST LABEL"
            }
        }
        
        # Define payment details
        payment_details = {
            "executionDateTime": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "expiryDateTime": (datetime.datetime.utcnow() + datetime.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "instructedAmount": 310,
            "transactionType": 38
        }
        
        # Define additional info
        info = {
            "stan": 123123,
            "rrn": "456456123123"
        }
        
        # Generate merchant QR code
        response = client.generate_dynamic_qrc_merchant(
            merchant_details=merchant_details,
            payer_details=payer_details,
            payment_details=payment_details,
            info=info
        )
        
        print("Merchant QR Code generated successfully")
        print(f"Response code: {response.get('responseCode')}")
        print(f"Description: {response.get('responseDescription')}")
        
    except Exception as e:
        print(f"Error generating merchant QR code: {str(e)}")
    
    # Example 2: Generate Aggregator QR Code
    try:
        # Define required details according to the aggregator API structure
        merchant_details = {
            "subDept": "3791001",
            "merchantID": "70425271300379"
        }
        
        contact_details = {
            "merchantChannelId": "400"
        }
        
        geo_location = {
            "lat": "24.875061",
            "long": "67.038332"
        }
        
        # For aggregator, payer_details includes payment_details and info nested inside
        payer_details = {
            "additionalRequiredDetails": "AME",
            "identificationDetails": {
                "loyaltyNo": "SOME LOYALTY NUMB",
                "customerLabel": "SOME CUST LABEL"
            },
            "paymentDetails": {
                "executionDateTime": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                "expiryDateTime": (datetime.datetime.utcnow() + datetime.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                "instructedAmount": "310",
                "transactionType": 38
            },
            "info": {
                "stan": "123123",
                "rrn": "456456123123"
            }
        }
        
        # Generate aggregator QR code
        response = client.generate_dynamic_qrc_aggregator(
            merchant_details=merchant_details,
            contact_details=contact_details,
            geo_location=geo_location,
            payer_details=payer_details
        )
        
        print("\nAggregator QR Code generated successfully")
        print(f"Response code: {response.get('responseCode')}")
        print(f"Description: {response.get('responseDescription')}")
        
    except Exception as e:
        print(f"Error generating aggregator QR code: {str(e)}")


def example_rtp_operations():
    """Examples of RTP transaction operations"""
    # Initialize the client
    client = OneLinkBaseClient(
        client_id="your_client_id_here",
        client_secret="your_client_secret_here",
        is_production=False
    )
    
    # Example 1: Generate RTP Now for merchant
    try:
        # Define merchant details
        merchant_details = {
            "dbaName": "SOME DBA NAME",
            "merchantName": "MERCHANT ACCOUNT TITLE",
            "iban": "PK81KHYB0022000001111111",
            "bankBic": "KHYB002",
            "merchantCategoryCode": "5411",
            "merchantID": "70425271300379",
            "postalAddress": {
                "townName": "KARACHI",
                "subDept": "3791001",
                "addressLine": "Free Format Address"
            },
            "contactDetails": {
                "phoneNo": "+92-3055520420",
                "mobileNo": "+92-3055520419",
                "email": "payee@karachi.pk",
                "dept": "SOME BRANCH",
                "website": "www.merchant.pk",
                "merchantChannelId": "400"
            },
            "geoLocation": {
                "lat": "24.875061",
                "long": "67.038332"
            }
        }
        
        # Define payer details
        payer_details = {
            "additionalRequiredDetails": "AME",
            "identificationDetails": {
                "loyaltyNo": "SOME LOYALTY NUMB",
                "customerLabel": "SOME CUST LABEL"
            }
        }
        
        # Define payment details with RTP ID
        payment_details = {
            "executionDateTime": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "expiryDateTime": (datetime.datetime.utcnow() + datetime.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "instructedAmount": 310,
            "rtpId": str(uuid.uuid4()),  # Generate a unique RTP ID
            "billNo": "1723471547"
        }
        
        # Define info
        info = {
            "stan": "123123",
            "rrn": "456456123123"
        }
        
        # Generate RTP Now request
        response = client.generate_rtp_now_merchant(
            merchant_details=merchant_details,
            payer_details=payer_details,
            payment_details=payment_details,
            info=info
        )
        
        print("RTP Now request for merchant generated successfully")
        print(f"Response code: {response.get('responseCode')}")
        print(f"Description: {response.get('responseDescription')}")
        
        # Store the RTP ID for later use in status check and cancellation
        rtp_id = payment_details["rtpId"]
        
    except Exception as e:
        print(f"Error generating RTP Now request for merchant: {str(e)}")
        rtp_id = "7f8de10f-fd48-412b-ae24-4ef7950972a6"  # Fallback RTP ID for examples
    
    # Example 2: Check status of an RTP transaction
    try:
        response = client.check_transaction_status(
            stan="cikigo",
            rtp_id=rtp_id,
            merchant_id="70425271300379",
            sub_dept="3791001"
        )
        
        print("\nRTP transaction status inquiry completed")
        print(f"Response code: {response.get('responseCode')}")
        print(f"Description: {response.get('responseDescription')}")
        
    except Exception as e:
        print(f"Error checking transaction status: {str(e)}")
    
    # Example 3: Cancel an RTP transaction
    try:
        response = client.cancel_rtp_transaction(
            stan="ehakar",
            rtp_id=rtp_id,
            merchant_id="70425271300379",
            sub_dept="3791001"
        )
        
        print("\nRTP transaction cancellation request submitted")
        print(f"Response code: {response.get('responseCode')}")
        print(f"Description: {response.get('responseDescription')}")
        
    except Exception as e:
        print(f"Error cancelling RTP transaction: {str(e)}")
    
    # Example 4: Generate RTP Later for merchant
    try:
        # Use the same details as RTP Now but with different dates
        payment_details["rtpId"] = str(uuid.uuid4())  # New RTP ID
        payment_details["executionDateTime"] = (datetime.datetime.utcnow() + datetime.timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        
        response = client.generate_rtp_later_merchant(
            merchant_details=merchant_details,
            payer_details=payer_details,
            payment_details=payment_details,
            info=info
        )
        
        print("\nRTP Later request for merchant generated successfully")
        print(f"Response code: {response.get('responseCode')}")
        print(f"Description: {response.get('responseDescription')}")
        
    except Exception as e:
        print(f"Error generating RTP Later request for merchant: {str(e)}")


if __name__ == "__main__":
    print("=== QR Code Generation Examples ===")
    example_qrc_generation()
    
    print("\n=== RTP Transaction Operations Examples ===")
    example_rtp_operations()