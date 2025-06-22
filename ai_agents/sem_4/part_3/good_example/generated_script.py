def calculate_days_for_iphone(monthly_salary):
	if monthly_salary <= 0:
		return 0
	price = 116990.0
	days_in_month = 22
	daily_earnings = monthly_salary / days_in_month
	days_needed = price / daily_earnings
	return round(days_needed)

if __name__ == '__main__':
	print(calculate_days_for_iphone(50000))