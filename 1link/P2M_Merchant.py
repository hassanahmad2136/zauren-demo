import requests
import json
from typing import Dict, Any, Optional, Union

def createMerchantProfile(
    client_id: str,
    token: str,
    dba_name: str,
    merchant_name: str,
    iban: str,
    bank_bic: str,
    merchant_category_code: str,
    merchant_id: Union[str, int],
    account_title: str,
    postal_address: Dict[str, Any],
    contact_details: Optional[Dict[str, Any]] = None,
    merchant_cnic: Optional[Union[str, int]] = None,
    merchant_cnic_expiry_date: Optional[str] = None,
    merchant_type: Optional[str] = None,
    payment_details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create a merchant profile using the 1Link API.
    
    Args:
        client_id (str): The X-IBM-Client-Id value
        token (str): Bearer token for authorization
        dba_name (str): Merchant "doing business as" name (max 140 chars)
        merchant_name (str): Merchant name or account title (max 140 chars)
        iban (str): Merchant IBAN (24 chars)
        bank_bic (str): Short BIC (6 chars)
        merchant_category_code (str): Merchant category code (4 chars)
        merchant_id (str or int): Unique Merchant ID (15 chars)
        account_title (str): Account title of the Merchant IBAN (max 140 chars)
        postal_address (Dict): Contains townName, addressLine, province, and optional subDept
        contact_details (Dict, optional): Contains optional phoneNo, mobileNo, email, dept, website
        merchant_cnic (str or int, optional): Merchant CNIC (max 13 chars)
        merchant_cnic_expiry_date (str, optional): Expiry date in ISO format
        merchant_type (str, optional): Type of merchant (max 50 chars)
        payment_details (Dict, optional): Contains feeValue and feeType
        
    Returns:
        Dict[str, Any]: API response as dictionary
    """
    # Validate required fields
    if not all([dba_name, merchant_name, iban, bank_bic, merchant_category_code, merchant_id, account_title]):
        raise ValueError("Missing required merchant details")
    
    # Validate postal_address required fields
    if not postal_address or not all(k in postal_address for k in ["townName", "addressLine", "province"]):
        raise ValueError("Missing required postal address fields")
    
    # Prepare request payload - match exactly the structure of the example
    payload = {
        "merchantDetails": {
            "dbaName": dba_name,
            "merchantName": merchant_name,
            "iban": iban,
            "bankBic": bank_bic,
            "merchantCategoryCode": merchant_category_code,
            "merchantID": merchant_id,  # Keep as passed (number or string)
            "accountTitle": account_title,
            "postalAddress": postal_address
        }
    }
    
    # Add optional fields if provided - exactly matching the example structure
    if contact_details:
        payload["merchantDetails"]["contactDetails"] = contact_details
    
    if merchant_cnic is not None:  # Allow 0 as valid
        payload["merchantDetails"]["merchantCnic"] = merchant_cnic
    
    if merchant_cnic_expiry_date:
        payload["merchantDetails"]["merchantCnicExpiryDate"] = merchant_cnic_expiry_date
    
    if merchant_type:
        payload["merchantDetails"]["merchantType"] = merchant_type
    
    if payment_details:
        payload["merchantDetails"]["paymentDetails"] = payment_details
    
    # API endpoint
    url = "https://sandboxapi.1link.net.pk/uat-1link/sandbox/1Link/createMerchantProfileVersion2"
    
    # Headers
    headers = {
        "X-IBM-Client-Id": client_id,
        "Authorization": f"Bearer {token}",
        "content-type": "application/json",
        "accept": "application/json"
    }
    
    # Make the API call with detailed logging
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
        response.raise_for_status()  # Raise exception for 4XX/5XX status codes
        
        if response.text:
            return response.json()
        return {"status": "success", "status_code": response.status_code}
        
    except requests.exceptions.RequestException as e:
        # Return more detailed error information
        error_info = {
            "error": str(e),
            "status_code": getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None,
            "response_text": getattr(e.response, 'text', None) if hasattr(e, 'response') else None
        }
        return error_info

# Example usage
if __name__ == "__main__":
    # Replace with actual values
    client_id = "0bbe0c132b6119d83dcf6b1bf6b280c0"
    token = "AAIgMGJiZTBjMTMyYjYxMTlkODNkY2Y2YjFiZjZiMjgwYzCHicUfpf3zVYXxX3Kzvt4exqval1zrY2nbDZ9b_ZdTqfgx3EIv0YL98G9sO3IKfOtyvU2MgjCoibGwwGObs9NkFagch0VgglqkClR8EkfSf1mKtkQQ0OOT609fNQsp_94"
    
    # This exactly matches the format in your example JSON
    response = createMerchantProfile(
        client_id=client_id,
        token=token,
        dba_name="SOME DBA NAME",
        merchant_name="MERCHANT ACCOUNT TITLE",
        iban="PK81KHYB0022000001111111",
        bank_bic="KHYB02",
        merchant_category_code="5411",
        merchant_id=704252713,  # Numeric as in your example
        account_title="ACCOUNT TITLE",
        postal_address={
            "townName": "Free Format Address",
            "addressLine": "Free Format Address",
            "province": "Sindh",
            "subDept": 1  # Numeric as in your example
        },
        contact_details={
            "phoneNo": "+92-3055520420",
            "mobileNo": "+92-3055520419",
            "email": "payee@karachi.pk",
            "dept": "SOME BRANCH",
            "website": "www.merchant.pk"
        },
        merchant_cnic=4210177404994,  # Numeric as in your example
        merchant_cnic_expiry_date="2024-12-01",
        merchant_type="Type of Merchant i.e. Utility",
        payment_details={
            "feeValue": 15,  # Numeric as in your example
            "feeType": "F"
        }
    )
    
    print(json.dumps(response, indent=2))