from generated_script import calculate_days_for_iphone

def test_calculate_days_for_iphone():
    assert calculate_days_for_iphone(50000) == 51, 'Неверное количество дней для зарплаты 50000'
    assert calculate_days_for_iphone(100000) == 26, 'Неверное количество дней для зарплаты 100000'
    assert calculate_days_for_iphone(0) == 0, 'Для зарплаты 0 должно быть возвращено 0'
    assert calculate_days_for_iphone(-50000) == 0, 'Для отрицательной зарплаты должно быть возвращено 0'