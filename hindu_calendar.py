"""
Hindu Calendar (Panchang) utility for the Payroll System
Provides Hindu date calculation and festival information
"""

from datetime import datetime, date
import calendar
import json

class HinduCalendar:
    """
    Hindu Calendar utility class for Panchang calculations
    Based on Purnimanta (North Indian) calendar system
    """
    
    # Hindu months (Purnimanta system)
    HINDU_MONTHS = [
        "Chaitra", "Vaishakha", "Jyeshtha", "Ashadha",
        "Shravana", "Bhadrapada", "Ashwin", "Kartik", 
        "Margashirsha", "Pausha", "Magha", "Phalguna"
    ]
    
    # Tithis (lunar days)
    TITHIS = [
        "Pratipada", "Dwitiya", "Tritiya", "Chaturthi", "Panchami",
        "Shashthi", "Saptami", "Ashtami", "Navami", "Dashami",
        "Ekadashi", "Dwadashi", "Trayodashi", "Chaturdashi", "Purnima"
    ]
    
    # Major festivals and their significance
    FESTIVALS = {
        "2024-03-25": {"name": "Holi", "significance": "Festival of Colors", "type": "festival"},
        "2024-04-09": {"name": "Ram Navami", "significance": "Birth of Lord Rama", "type": "festival"},
        "2024-04-17": {"name": "Hanuman Jayanti", "significance": "Birth of Lord Hanuman", "type": "festival"},
        "2024-08-19": {"name": "Janmashtami", "significance": "Birth of Lord Krishna", "type": "festival"},
        "2024-09-07": {"name": "Ganesh Chaturthi", "significance": "Birth of Lord Ganesha", "type": "festival"},
        "2024-10-02": {"name": "Gandhi Jayanti", "significance": "National Holiday", "type": "national"},
        "2024-10-12": {"name": "Dussehra", "significance": "Victory of Good over Evil", "type": "festival"},
        "2024-11-01": {"name": "Diwali", "significance": "Festival of Lights", "type": "festival"},
        "2024-11-15": {"name": "Bhai Dooj", "significance": "Brother-Sister Festival", "type": "festival"},
        # Add Amavasya (New Moon) dates for 2024-2025
        "2024-01-11": {"name": "Amavasya", "significance": "New Moon Day", "type": "lunar"},
        "2024-02-09": {"name": "Amavasya", "significance": "New Moon Day", "type": "lunar"},
        "2024-03-10": {"name": "Amavasya", "significance": "New Moon Day", "type": "lunar"},
        "2024-04-08": {"name": "Amavasya", "significance": "New Moon Day", "type": "lunar"},
        "2024-05-08": {"name": "Amavasya", "significance": "New Moon Day", "type": "lunar"},
        "2024-06-06": {"name": "Amavasya", "significance": "New Moon Day", "type": "lunar"},
        "2024-07-05": {"name": "Amavasya", "significance": "New Moon Day", "type": "lunar"},
        "2024-08-04": {"name": "Amavasya", "significance": "New Moon Day", "type": "lunar"},
        "2024-09-03": {"name": "Amavasya", "significance": "New Moon Day", "type": "lunar"},
        "2024-10-02": {"name": "Amavasya", "significance": "New Moon Day", "type": "lunar"},
        "2024-11-01": {"name": "Amavasya", "significance": "New Moon Day (Diwali)", "type": "lunar"},
        "2024-12-01": {"name": "Amavasya", "significance": "New Moon Day", "type": "lunar"},
        "2024-12-30": {"name": "Amavasya", "significance": "New Moon Day", "type": "lunar"},
        # 2025 festivals
        "2025-03-14": {"name": "Holi", "significance": "Festival of Colors", "type": "festival"},
        "2025-03-30": {"name": "Ram Navami", "significance": "Birth of Lord Rama", "type": "festival"},
        "2025-04-06": {"name": "Hanuman Jayanti", "significance": "Birth of Lord Hanuman", "type": "festival"},
        "2025-08-16": {"name": "Janmashtami", "significance": "Birth of Lord Krishna", "type": "festival"},
        "2025-08-27": {"name": "Ganesh Chaturthi", "significance": "Birth of Lord Ganesha", "type": "festival"},
        "2025-10-02": {"name": "Gandhi Jayanti", "significance": "National Holiday", "type": "national"},
        "2025-10-22": {"name": "Dussehra", "significance": "Victory of Good over Evil", "type": "festival"},
        "2025-11-01": {"name": "Diwali", "significance": "Festival of Lights", "type": "festival"},
        "2025-11-03": {"name": "Bhai Dooj", "significance": "Brother-Sister Festival", "type": "festival"},
        # 2025 Amavasya dates
        "2025-01-29": {"name": "Amavasya", "significance": "New Moon Day", "type": "lunar"},
        "2025-02-28": {"name": "Amavasya", "significance": "New Moon Day", "type": "lunar"},
        "2025-03-29": {"name": "Amavasya", "significance": "New Moon Day", "type": "lunar"},
        "2025-04-27": {"name": "Amavasya", "significance": "New Moon Day", "type": "lunar"},
        "2025-05-27": {"name": "Amavasya", "significance": "New Moon Day", "type": "lunar"},
        "2025-06-25": {"name": "Amavasya", "significance": "New Moon Day", "type": "lunar"},
        "2025-07-24": {"name": "Amavasya", "significance": "New Moon Day", "type": "lunar"},
        "2025-08-23": {"name": "Amavasya", "significance": "New Moon Day", "type": "lunar"},
        "2025-09-21": {"name": "Amavasya", "significance": "New Moon Day", "type": "lunar"},
        "2025-10-21": {"name": "Amavasya", "significance": "New Moon Day", "type": "lunar"},
        "2025-11-20": {"name": "Amavasya", "significance": "New Moon Day", "type": "lunar"},
        "2025-12-19": {"name": "Amavasya", "significance": "New Moon Day", "type": "lunar"},
    }
    
    # Shraddha period (Pitru Paksha) - approximate dates
    SHRADDHA_PERIODS = {
        "2024": ("2024-09-17", "2024-10-02"),
        "2025": ("2025-09-06", "2025-09-21"),
    }
    
    def __init__(self):
        """Initialize Hindu Calendar"""
        pass
    
    def get_vikram_samvat(self, date_obj=None):
        """
        Get Vikram Samvat year
        Vikram Samvat starts around April, so:
        - Jan-Mar: Gregorian year + 56
        - Apr-Dec: Gregorian year + 57
        """
        if date_obj is None:
            date_obj = date.today()
        
        gregorian_year = date_obj.year
        
        # Simplified calculation - in reality, it depends on the exact start of Chaitra
        if date_obj.month <= 3:
            return gregorian_year + 56
        else:
            return gregorian_year + 57
    
    def get_hindu_month_approximate(self, date_obj=None):
        """
        Get approximate Hindu month based on Gregorian date
        This is a simplified mapping - actual calculation requires lunar positions
        """
        if date_obj is None:
            date_obj = date.today()
        
        # Simplified mapping (approximate)
        month_mapping = {
            1: "Pausha", 2: "Magha", 3: "Phalguna", 4: "Chaitra",
            5: "Vaishakha", 6: "Jyeshtha", 7: "Ashadha", 8: "Shravana",
            9: "Bhadrapada", 10: "Ashwin", 11: "Kartik", 12: "Margashirsha"
        }
        
        return month_mapping.get(date_obj.month, "Chaitra")
    
    def get_paksha_and_tithi_approximate(self, date_obj=None):
        """
        Get approximate Paksha (fortnight) and Tithi (lunar day)
        This is a simplified calculation based on the day of month
        """
        if date_obj is None:
            date_obj = date.today()
        
        # Simplified calculation based on date
        day = date_obj.day
        
        # Approximate mapping - in reality this needs lunar calendar calculation
        if day <= 15:
            paksha = "Shukla Paksha"  # Bright fortnight
            tithi_index = (day - 1) % 15
        else:
            paksha = "Krishna Paksha"  # Dark fortnight
            tithi_index = (day - 16) % 15
        
        tithi = self.TITHIS[tithi_index] if tithi_index < len(self.TITHIS) else "Purnima"
        
        return paksha, tithi
    
    def get_festival_info(self, date_obj=None):
        """Check if the given date is a festival"""
        if date_obj is None:
            date_obj = date.today()
        
        date_str = date_obj.strftime("%Y-%m-%d")
        return self.FESTIVALS.get(date_str)
    
    def is_shraddha_period(self, date_obj=None):
        """Check if the date falls in Shraddha/Pitru Paksha period"""
        if date_obj is None:
            date_obj = date.today()
        
        year = str(date_obj.year)
        if year in self.SHRADDHA_PERIODS:
            start_date = datetime.strptime(self.SHRADDHA_PERIODS[year][0], "%Y-%m-%d").date()
            end_date = datetime.strptime(self.SHRADDHA_PERIODS[year][1], "%Y-%m-%d").date()
            return start_date <= date_obj <= end_date
        
        return False
    
    def get_panchang_summary(self, date_obj=None):
        """Get complete Panchang summary for a date"""
        if date_obj is None:
            date_obj = date.today()
        
        hindu_month = self.get_hindu_month_approximate(date_obj)
        vikram_samvat = self.get_vikram_samvat(date_obj)
        paksha, tithi = self.get_paksha_and_tithi_approximate(date_obj)
        festival = self.get_festival_info(date_obj)
        is_shraddha = self.is_shraddha_period(date_obj)
        
        return {
            "gregorian_date": date_obj.strftime("%Y-%m-%d"),
            "hindu_month": hindu_month,
            "vikram_samvat": vikram_samvat,
            "paksha": paksha,
            "tithi": tithi,
            "festival": festival,
            "is_shraddha": is_shraddha,
            "formatted_hindu_date": f"{hindu_month}, {paksha}, {tithi}, Vikram Samvat {vikram_samvat}"
        }
    
    def get_month_festivals(self, year, month):
        """Get all festivals for a specific month"""
        festivals = []
        
        # Get number of days in the month
        _, days_in_month = calendar.monthrange(year, month)
        
        for day in range(1, days_in_month + 1):
            check_date = date(year, month, day)
            festival = self.get_festival_info(check_date)
            if festival:
                festivals.append({
                    "date": check_date.strftime("%Y-%m-%d"),
                    "day": day,
                    "festival": festival
                })
        
        return festivals
    
    def get_suggested_holidays(self, year, month):
        """Get suggested holidays for admin to add (festivals + Amavasya)."""
        suggestions = []
        
        # Get all festivals for the month
        festivals = self.get_month_festivals(year, month)
        
        for festival_data in festivals:
            festival = festival_data['festival']
            suggestions.append({
                'date': festival_data['date'],
                'name': festival['name'],
                'type': festival.get('type', 'festival'),
                'description': festival['significance'],
                'is_suggested': True
            })
        
        return suggestions

# Create a global instance
hindu_calendar = HinduCalendar()