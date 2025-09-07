import requests
import json
import datetime
import uuid
from typing import Dict, Any, Optional, List, Union

# Import the base client to extend it
from 1link_base_client import OneLinkBaseClient


class OneLinkMerchantClient(OneLinkBaseClient):
    """
    Merchant management client for 1Link API, extending the base client with:
    - Merchant profile creation and management
    - Merchant notification handling
    """
    
    def __init__(
        self, 
        client_id: str,
        client_secret: str,
        is_production: bool = False
    ):
        """
        Initialize the 1Link Merchant API client.
        
        Args:
            client_id: The X-IBM-Client-Id for API authentication
            client_secret: The client secret for OAuth authentication
            is_production: Flag to determine whether to use production or sandbox environment
        """
        # Initialize the base client
        super().__init__(client_id, client_secret, is_production)
        
        # Merchant profile management endpoints
        self.create_merchant_profile_url = f"{self.base_url}/1Link/createMerchantProfile"
        self.create_merchant_profile_v2_url = f"{self.base_url}/1Link/createMerchantProfileVersion2"
        self.get_merchant_profile_url = f"{self.base_url}/1Link/getMerchantProfile"
        self.update_merchant_profile_url = f"{self.base_url}/1Link/updateMerchantProfile"
        
        # Merchant notification endpoints
        self.notify_merchant_url = f"{self.base_url}/1Link/notifyMerchant"
        self.payment_notification_url = f"{self.base_url}/1Link/paymentNotification"
    
    # =====================================================================
    # Merchant Profile Management Methods
    # =====================================================================
    
    def create_merchant_profile(
        self,
        merchant_details: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a new merchant profile.
        
        Args:
            merchant_details: Dictionary containing complete merchant information
            
        Returns:
            Dict[str, Any]: The API response with merchant creation status
        """
        # Prepare request payload
        payload = {
            "merchantDetails": merchant_details
        }
        
        return self._make_api_request(self.create_merchant_profile_url, payload)
    
    def create_merchant_profile_v2(
        self,
        merchant_details: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a new merchant profile using version 2 of the API.
        This version includes additional fields like CNIC and merchant type.
        
        Args:
            merchant_details: Dictionary containing complete merchant information
            
        Returns:
            Dict[str, Any]: The API response with merchant creation status
        """
        # Prepare request payload
        payload = {
            "merchantDetails": merchant_details
        }
        
        return self._make_api_request(self.create_merchant_profile_v2_url, payload)
    
    def get_merchant_profile(
        self,
        merchant_id: str
    ) -> Dict[str, Any]:
        """
        Retrieve a merchant's profile details.
        
        Args:
            merchant_id: The ID of the merchant
            
        Returns:
            Dict[str, Any]: The API response with merchant profile details
        """
        # For GET requests, we need to handle the URL params differently
        token = self._ensure_valid_token()
        
        # Prepare headers
        headers = {
            "X-IBM-Client-Id": self.client_id,
            "Authorization": f"Bearer {token}",
            "Accept": "application/json"
        }
        
        # Prepare query parameters
        params = {
            "merchantID": merchant_id
        }
        
        # Make the API request
        response = requests.get(
            self.get_merchant_profile_url,
            headers=headers,
            params=params
        )
        
        # Check for successful response
        if response.status_code != 200:
            raise Exception(f"Failed to get merchant profile: {response.status_code} - {response.text}")
        
        return response.json()
    
    def update_merchant_profile(
        self,
        merchant_details: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update an existing merchant's profile.
        
        Args:
            merchant_details: Dictionary containing complete merchant information
            
        Returns:
            Dict[str, Any]: The API response with merchant update status
        """
        # Prepare request payload
        payload = {
            "merchantDetails": merchant_details
        }
        
        return self._make_api_request(self.update_merchant_profile_url, payload)
    
    # =====================================================================
    # Merchant Notification Methods
    # =====================================================================
    
    def notify_merchant(
        self,
        info: Dict[str, Any],
        message_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Notify a merchant about the status of a transaction.
        
        Args:
            info: Dictionary containing reference information (rrn, stan, dateTime)
            message_info: Dictionary containing detailed message information
            
        Returns:
            Dict[str, Any]: The API response with notification status
        """
        # Prepare request payload
        payload = {
            "info": info,
            "messageInfo": message_info
        }
        
        return self._make_api_request(self.notify_merchant_url, payload)
    
    def send_payment_notification(
        self,
        info: Dict[str, Any],
        message_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Send a payment notification to a merchant or merchant aggregator.
        This is used for instant settlement notifications.
        
        Args:
            info: Dictionary containing reference information (rrn, stan, dateTime)
            message_info: Dictionary containing detailed payment information
            
        Returns:
            Dict[str, Any]: The API response with notification status
        """
        # Prepare request payload
        payload = {
            "info": info,
            "messageInfo": message_info
        }
        
        return self._make_api_request(self.payment_notification_url, payload)


# =====================================================================
# Usage Examples
# =====================================================================

def example_merchant_profile_management():
    """Examples of merchant profile management operations"""
    # Initialize the client
    client = OneLinkMerchantClient(
        client_id="your_client_id_here",
        client_secret="your_client_secret_here",
        is_production=False
    )
    
    # Example 1: Create a merchant profile (V2)
    try:
        # Define merchant details with CNIC and additional fields for V2
        merchant_details = {
            "dbaName": "SOME DBA NAME",
            "merchantName": "MERCHANT ACCOUNT TITLE",
            "iban": "PK81KHYB0022000001111111",
            "bankBic": "KHYB02",
            "merchantCategoryCode": "5411",
            "merchantID": 70425271300379,
            "accountTitle": "ACCOUNT TITLE",
            "postalAddress": {
                "townName": "Free Format Address",
                "addressLine": "Free Format Address",
                "province": "Sindh",
                "subDept": 1
            },
            "contactDetails": {
                "phoneNo": "+92-3055520420",
                "mobileNo": "+92-3055520419",
                "email": "payee@karachi.pk",
                "dept": "SOME BRANCH",
                "website": "www.merchant.pk"
            },
            "merchantCnic": 4210177404994,
            "merchantCnicExpiryDate": "2024-12-01T00:00:00.000Z",
            "merchantType": "Type of Merchant i.e. Utility",
            "paymentDetails": {
                "feeValue": 15,
                "feeType": "F"
            }
        }
        
        response = client.create_merchant_profile_v2(merchant_details)
        
        print("Merchant profile created successfully")
        print(f"Response code: {response.get('responseCode')}")
        print(f"Description: {response.get('responseDescription')}")
        
    except Exception as e:
        print(f"Error creating merchant profile: {str(e)}")
    
    # Example 2: Get merchant profile
    try:
        # Use the merchant ID from the creation step or a known ID
        merchant_id = "70425271300379"
        
        response = client.get_merchant_profile(merchant_id)
        
        print("\nMerchant profile retrieved successfully")
        print(f"Response code: {response.get('responseCode')}")
        print(f"Description: {response.get('responseDescription')}")
        
        # You would typically process the merchant details here
        # The response would contain the full merchant profile
        
    except Exception as e:
        print(f"Error retrieving merchant profile: {str(e)}")
    
    # Example 3: Update merchant profile
    try:
        # Update some fields in the merchant profile
        update_details = {
            "merchantCnic": 4210177404994,
            "merchantCnicExpiryDate": "2024-12-01T00:00:00.000Z",
            "merchantType": "Proximity",
            "dbaName": "UPDATED DBA NAME",
            "merchantName": "MERCHANT ACCOUNT TITLE",
            "merchantStatus": "00",
            "reasonCode": "002",
            "iban": "PK81KHYB0022000001111111",
            "bankBic": "KHYB02",
            "merchantCategoryCode": "5411",
            "merchantID": "70425271300379",
            "accountTitle": "ACCOUNT TITLE",
            "postalAddress": {
                "townName": "Free Format Address",
                "addressLine": "Free Format Address",
                "province": "Sindh"
            },
            "contactDetails": {
                "phoneNo": "+92-3055520420",
                "mobileNo": "+92-3055520419",
                "email": "payee@karachi.pk",
                "dept": "SOME BRANCH",
                "website": "www.merchant.pk"
            },
            "paymentDetails": {
                "feeType": "F",
                "feeValue": "15"
            }
        }
        
        response = client.update_merchant_profile({"merchantDetails": update_details})
        
        print("\nMerchant profile updated successfully")
        print(f"Response code: {response.get('responseCode')}")
        print(f"Description: {response.get('responseDescription')}")
        
    except Exception as e:
        print(f"Error updating merchant profile: {str(e)}")


def example_merchant_notifications():
    """Examples of merchant notification operations"""
    # Initialize the client
    client = OneLinkMerchantClient(
        client_id="your_client_id_here",
        client_secret="your_client_secret_here",
        is_production=False
    )
    
    # Example 1: Notify merchant about transaction status
    try:
        # Define information for notification
        info = {
            "rrn": "10123010123",
            "stan": "10123",
            "dateTime": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z")
        }
        
        message_info = {
            "orginalRRN": "150425014123",
            "orginalStan": "14123",
            "originalMessageId": "94252f443385470eb5f79dd0f8cc1bbf",
            "originalRtpId": "7f8de10f-fd48-412b-ae24-4ef7950972a6",
            "merchantID": "70425271300379",
            "subDept": "3791001",
            "status": "RTP Accepted"
        }
        
        response = client.notify_merchant(info, message_info)
        
        print("Merchant notification sent successfully")
        print(f"Response code: {response.get('responseCode')}")
        print(f"Description: {response.get('responseDescription')}")
        
    except Exception as e:
        print(f"Error notifying merchant: {str(e)}")
    
    # Example 2: Send payment notification for instant settlement
    try:
        # Define information for payment notification
        info = {
            "rrn": "10123010123",
            "stan": "10123",
            "dateTime": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z")
        }
        
        message_info = {
            "orginalRRN": "150425014123",
            "orginalStan": "14123",
            "messageId": "94252f443385470eb5f79dd0f8cc1bbf",
            "originalRtpId": "7f8de10f-fd48-412b-ae24-4ef7950972a6",
            "merchantID": "70425271300379",
            "subDept": "3791001",
            "status": "Payment Sent",
            "orginalInstructedAmount": 1000,
            "netAmount": 980
        }
        
        response = client.send_payment_notification(info, message_info)
        
        print("\nPayment notification sent successfully")
        print(f"Response code: {response.get('responseCode')}")
        print(f"Description: {response.get('responseDescription')}")
        
    except Exception as e:
        print(f"Error sending payment notification: {str(e)}")


if __name__ == "__main__":
    print("=== Merchant Profile Management Examples ===")
    example_merchant_profile_management()
    
    print("\n=== Merchant Notification Examples ===")
    example_merchant_notifications()