import decimal

def round_half_up(value, decimals=0):
    if value is None:
        return None
        
    decimal_value = decimal.Decimal(str(value))
    rounding_factor = decimal.Decimal('10') ** decimals
    
    rounded_decimal = decimal_value.quantize(
        decimal.Decimal('1') / rounding_factor,
        rounding=decimal.ROUND_HALF_UP
    )
    
    return float(rounded_decimal)
