import re

def get_number_from_currency_string(currency: str) -> float:
    """
    Convert currency string like "1 Crore", "10 Lakhs" to number
    """
    try:
        if "crore" in currency.lower():
            number_str = re.sub("[^0-9.]", "", currency)
            return float(number_str) * 10000000
        elif "lakh" in currency.lower():
            number_str = re.sub("[^0-9.]", "", currency)
            return float(number_str) * 100000
        elif "thousand" in currency.lower():
            number_str = re.sub("[^0-9.]", "", currency)
            return float(number_str) * 1000
        else:
            currency = currency.split(".")[0]
            regexed = re.sub("[^0-9.]", "", currency)
            if regexed:
                return float(regexed)
            else:
                return 0.0

    except Exception as e:
        print(e)
        return 0.0
