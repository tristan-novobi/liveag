# Copyright © 2024 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _

class DeliverySlideMixin(models.AbstractModel):
    """Mixin for slide-related calculations in delivery"""
    _name = 'delivery.slide.mixin'
    _description = 'Delivery Slide Calculation Mixin'

    # Slide Information
    price_adjustment = fields.Float(
        string='Price Adjustment',
        compute='_compute_price_adjustment',
        store=True,
        help='Price adjustment based on slide')
    
    adjusted_price = fields.Float(
        string='Adjusted Price',
        compute='_compute_adjusted_price',
        store=True,
        help='Price after slide adjustment')
    
    # Gain Slide Specific Fields
    is_gain_slide = fields.Boolean(
        string='Is Gain Slide',
        compute='_compute_is_gain_slide',
        store=True,
        help='True if slide type is Gain Slide')
    
    gain_price = fields.Float(
        string='Gain Price',
        help='Price per pound for weight gain')
    
    base_weight_payment = fields.Float(
        string='Base Weight Payment',
        compute='_compute_gain_slide_payments',
        store=True,
        help='Payment for base weight in gain slide')
    
    weight_gain = fields.Float(
        string='Weight Gain',
        compute='_compute_gain_slide_payments',
        store=True,
        help='Total weight gain above base weight')
    
    weight_gain_payment = fields.Float(
        string='Weight Gain Payment',
        compute='_compute_gain_slide_payments',
        store=True,
        help='Payment for weight gain in gain slide')
    
    # Computed Methods
    def _compute_is_gain_slide(self):
        """Determine if this is a gain slide
        
        This method should be implemented in the main model to set the is_gain_slide
        flag based on the slide_type_name field.
        
        Example implementation:
        ```
        for record in self:
            record.is_gain_slide = record.slide_type_name == 'Gain'
        ```
        """
        pass
    
    def _compute_gain_slide_payments(self):
        """Calculate payments for gain slide
        
        This method should be implemented in the main model to calculate:
        1. base_weight_payment: Payment for the base weight
        2. weight_gain: Total weight gain above base weight
        3. weight_gain_payment: Payment for the weight gain
        
        Example implementation:
        ```
        for record in self:
            # Skip calculation if not a gain slide or missing required data
            if not record.is_gain_slide or not record.head_count or not record.contract_weight:
                record.base_weight_payment = 0.0
                record.weight_gain = 0.0
                record.weight_gain_payment = 0.0
                continue
                
            # Calculate base weight total
            base_weight_total = record.head_count * float(record.contract_weight)
            
            # Calculate payment for base weight
            record.base_weight_payment = base_weight_total * record.base_price / 100
            
            # Calculate weight gain (ensure non-negative)
            record.weight_gain = max(0, record.net_weight - base_weight_total)
            
            # Calculate payment for weight gain
            record.weight_gain_payment = record.weight_gain * record.gain_price
        ```
        
        Example calculation:
        - Base weight: 300 lbs
        - Head count: 150 steers
        - Base price: $350.00/cwt
        - Gain price: $1.00/lb
        - Total net weight: 48,240 lbs
        
        1. Base weight total: 150 × 300 = 45,000 lbs
        2. Weight gain: 48,240 - 45,000 = 3,240 lbs
        3. Payment for base weight: 45,000 × $350.00 ÷ 100 = $157,500.00
        4. Payment for weight gain: 3,240 × $1.00 = $3,240.00
        5. Total payment: $157,500.00 + $3,240.00 = $160,740.00
        """
        pass
    
    def _compute_price_adjustment(self):
        """Calculate price adjustment based on slide type and weight difference
        
        This method should be implemented in the main model to calculate the price
        adjustment based on the slide type, slide values, and weight difference.
        
        Example implementation:
        ```
        for record in self:
            record.price_adjustment = self._calculate_price_adjustment(
                record.slide_type_name,
                record.slide_over,
                record.slide_under,
                record.slide_both,
                record.adjusted_weight_difference,
                record.is_overweight,
                record.is_underweight
            )
        ```
        """
        pass
    
    def _calculate_price_adjustment(self, slide_type_name, slide_over, slide_under, slide_both, 
                                  adjusted_weight_difference, is_overweight, is_underweight,
                                  contract_weight=None, weight_stop=None, weight_stop_value=None):
        """Calculate price adjustment based on slide type and weight difference
        
        This method calculates the price adjustment (in dollars per cwt) based on the slide type,
        slide values, and the difference between actual and contract weight.
        
        Slide Types and Calculations:
        
        1. Conventional Slide:
           - Only applies when cattle are overweight
           - Formula: Adjusted Price = Base Price - (Slide¢ × (Actual Avg Weight - Contract Avg Weight) ÷ 100)
           - Example: Base weight 850 lbs, Slide 10¢, Base price $250.00/cwt, Actual weight 865 lbs
             Calculation: 865 - 850 = 15 lbs over at 10¢ = $1.50
             Adjusted price: $250.00 - $1.50 = $248.50/cwt
        
        2. Two-Way Slide:
           - Applies when cattle are either overweight or underweight
           - Overweight Formula: Adjusted Price = Base Price - (Slide¢ × (Actual Avg Weight - Contract Avg Weight) ÷ 100)
           - Underweight Formula: Adjusted Price = Base Price + (Slide¢ × (Contract Avg Weight - Actual Avg Weight) ÷ 100)
           - Example (Overweight): Base weight 850 lbs, Slide 10¢, Base price $250.00/cwt, Actual weight 865 lbs
             Calculation: 865 - 850 = 15 lbs over at 10¢ = $1.50
             Adjusted price: $250.00 - $1.50 = $248.50/cwt
           - Example (Underweight): Base weight 850 lbs, Slide 10¢, Base price $250.00/cwt, Actual weight 835 lbs
             Calculation: 850 - 835 = 15 lbs under at 10¢ = $1.50
             Adjusted price: $250.00 + $1.50 = $251.50/cwt
        
        3. LiveAg Two-Way Slide:
           - Functions the same as Two-Way slide but the underweight adjustment uses half the slide value
           - Overweight Formula: Adjusted Price = Base Price - (Slide¢ × (Actual Avg Weight - Contract Avg Weight) ÷ 100)
           - Underweight Formula: Adjusted Price = Base Price + ((Slide¢ ÷ 2) × (Contract Avg Weight - Actual Avg Weight) ÷ 100)
           - Example (Overweight): Base weight 850 lbs, Slide 10¢ up/5¢ down, Base price $250.00/cwt, Actual weight 865 lbs
             Calculation: 865 - 850 = 15 lbs over at 10¢ = $1.50
             Adjusted price: $250.00 - $1.50 = $248.50/cwt
           - Example (Underweight): Base weight 850 lbs, Slide 10¢ up/5¢ down, Base price $250.00/cwt, Actual weight 835 lbs
             Calculation: 850 - 835 = 15 lbs under at 5¢ = $0.75
             Adjusted price: $250.00 + $0.75 = $250.75/cwt
        
        4. Both Slide:
           - Similar to Two-Way but uses the same slide value for both overweight and underweight
           - Overweight Formula: Adjusted Price = Base Price - (Slide¢ × (Actual Avg Weight - Contract Avg Weight) ÷ 100)
           - Underweight Formula: Adjusted Price = Base Price + (Slide¢ × (Contract Avg Weight - Actual Avg Weight) ÷ 100)
        
        5. Gain Slide:
           - Completely different calculation method, handled separately
           - Formula:
             1. Payment for base weight: Head Count × Base Weight × Base Price ÷ 100
             2. Payment for weight gain: (Total Net Weight - (Head Count × Base Weight)) × Gain Price
             3. Total payment: Payment for base weight + Payment for weight gain
           - Example: Base weight 300 lbs, Head count 150 steers, Base price $350.00/cwt, Gain price $1.00/lb
             Base weight total: 150 × 300 = 45,000 lbs
             Weight gain: 48,240 - 45,000 = 3,240 lbs
             Payment for base weight: 45,000 × $350.00 ÷ 100 = $157,500.00
             Payment for weight gain: 3,240 × $1.00 = $3,240.00
             Total payment: $157,500.00 + $3,240.00 = $160,740.00
        
        Args:
            slide_type_name (str): Name of the slide type
            slide_over (float): Slide amount for overweight
            slide_under (float): Slide amount for underweight
            slide_both (float): Slide amount for both over and under
            adjusted_weight_difference (float): Weight difference from contract weight
            is_overweight (bool): Whether the weight is over contract weight
            is_underweight (bool): Whether the weight is under contract weight
            contract_weight (float): Contract weight for gain slide calculations
            weight_stop (str): Name of the weight stop ('None', 'True Stop', etc.)
            weight_stop_value (float): Value of the weight stop
            
        Returns:
            float: Price adjustment amount
        """
        # Return 0 if no slide type or no weight difference
        if not slide_type_name or not adjusted_weight_difference:
            return 0.0
            
        # Handle different slide types
        if slide_type_name == 'none':
            return 0.0
            
        if slide_type_name == 'Gain Slide':
            # Gain slide uses a different calculation method handled in _compute_gain_slide_payments
            return 0.0
            
        if slide_type_name == 'conventional':
            if is_overweight:
                # Limit weight difference if there is a weight stop
                if weight_stop != 'None' and adjusted_weight_difference > weight_stop_value:
                    adjusted_weight_difference = weight_stop_value
                # Conventional slide only applies when cattle are overweight
                return (float(slide_over) * adjusted_weight_difference) / 100
            elif is_underweight:
                # Conventional slide for underweight
                return (float(slide_under) * abs(adjusted_weight_difference)) / 100
                
        if slide_type_name == 'two-way':
            if is_overweight:
                # Limit weight difference if there is a weight stop
                if weight_stop != 'None' and adjusted_weight_difference > weight_stop_value:
                    adjusted_weight_difference = weight_stop_value
                return (float(slide_both) * adjusted_weight_difference) / 100
            elif is_underweight:
                # Limit weight difference if there is a weight stop
                if weight_stop != 'None' and abs(adjusted_weight_difference) > weight_stop_value:
                    adjusted_weight_difference = weight_stop_value
                return (float(slide_both) * abs(adjusted_weight_difference)) / 100
                
        if slide_type_name == 'la_two-way':
            if is_overweight:
                # Limit weight difference if there is a weight stop
                if weight_stop != 'None' and adjusted_weight_difference > weight_stop_value:
                    adjusted_weight_difference = weight_stop_value
                return (float(slide_over) * adjusted_weight_difference) / 100
            elif is_underweight:
                # Limit weight difference if there is a weight stop
                if weight_stop != 'None' and abs(adjusted_weight_difference) > weight_stop_value:
                    adjusted_weight_difference = weight_stop_value
                return (float(slide_under) * abs(adjusted_weight_difference)) / 100
                
        return 0.0
    
    def _compute_adjusted_price(self):
        """Calculate adjusted price after slide adjustment
        
        This method should be implemented in the main model to calculate the
        adjusted price by applying the price adjustment to the base price.
        
        Example implementation:
        ```
        for record in self:
            adjustment_factor = -1 if record.is_overweight else 1
            record.adjusted_price = record.base_price + (adjustment_factor * record.price_adjustment)
        ```
        
        Example calculations:
        
        1. Conventional Slide (Overweight):
           - Base price: $250.00/cwt
           - Price adjustment: $1.50/cwt
           - Adjusted price: $250.00 - $1.50 = $248.50/cwt
        
        2. Two-Way Slide (Underweight):
           - Base price: $250.00/cwt
           - Price adjustment: $1.50/cwt
           - Adjusted price: $250.00 + $1.50 = $251.50/cwt
        """
        pass