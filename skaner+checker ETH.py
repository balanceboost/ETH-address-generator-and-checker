import os
import aiofiles
import asyncio
import hashlib
import time  # Добавлено для работы с временем
from multiprocessing import Manager, Process
import pyfiglet
from termcolor import colored
from eth_utils import keccak

# Файлы для работы
RICH_FILE = 'RichETH.txt'
FOUND_FILE = 'FoundETH.txt'
STATE_FILE = 'state_eth.txt'

# Чтение состояния
async def read_state():
    if os.path.exists(STATE_FILE):
        async with aiofiles.open(STATE_FILE, 'r') as f:
            state = await f.read()  # Читаем содержимое
            try:
                return int(state.strip()) if state.strip() else 0  # Убираем пробелы и проверяем
            except ValueError:
                print("Ошибка: состояние не является целым числом. Устанавливаем состояние в 0.")
                return 0  # Возвращаем 0, если возникла ошибка
    return 0  # Возвращаем 0, если файл пуст или не существует

# Сохранение состояния
async def save_state(state):
    async with aiofiles.open(STATE_FILE, 'w') as f:
        await f.write(str(state))

# Генерация ETH-адреса на основе приватного ключа
def private_key_to_eth_address(private_key):
    public_key = keccak(private_key).hex()[-40:]  # Используем последние 40 символов keccak хэша
    eth_address = '0x' + public_key
    return eth_address

# Генерация приватного ключа и адреса ETH с высокой энтропией
def generate_eth_address_high_entropy():
    private_key = os.urandom(32)  # Генерация случайного приватного ключа (32 байта)
    eth_address = private_key_to_eth_address(private_key)
    return private_key, eth_address

# Генерация приватного ключа и адреса ETH с низкой энтропией
def generate_eth_address_low_entropy():
    private_key = os.urandom(16)  # Генерация приватного ключа с низкой энтропией (16 байт)
    private_key = private_key.ljust(32, b'\0')  # Дополняем до 32 байт для совместимости
    eth_address = private_key_to_eth_address(private_key)
    return private_key, eth_address

# Функция для генерации адресов в зависимости от выбора метода
def generate_eth_address(method='high'):
    if method == 'low':
        return generate_eth_address_low_entropy()
    else:
        return generate_eth_address_high_entropy()

# Асинхронная функция для записи найденных адресов в файл
async def write_found_address(address, private_key):
    async with aiofiles.open(FOUND_FILE, 'a') as f:
        await f.write(f'{address}, {private_key.hex()}\n')

# Функция для проверки адресов
async def check_addresses(worker_id, start_state, progress_dict, rich_addresses, method):
    found = 0
    generated = 0
    state = start_state

    while True:  # Бесконечный цикл генерации и проверки адресов
        private_key, eth_address = generate_eth_address(method)

        generated += 1
        if eth_address in rich_addresses:  # Проверка на наличие адреса в rich_addresses
            await write_found_address(eth_address, private_key)  # Асинхронная запись
            found += 1

        # Обновление прогресса для текущего потока
        progress_dict[worker_id] = (generated, found)

        # Периодическое сохранение прогресса в файл
        if generated % 100000 == 0:
            await save_state(state)
        state += 1

# Процесс вывода статистики
def print_progress(progress_dict):
    start_time = time.time()
    total_generated = 0
    total_found = 0

    while True:
        time.sleep(1)  # Обновление каждые 1 секунду
        total_generated = sum([val[0] for val in progress_dict.values()])
        total_found = sum([val[1] for val in progress_dict.values()])
        elapsed_time = time.time() - start_time
        speed = total_generated / elapsed_time if elapsed_time > 0 else 0

        # Формируем весь вывод с окрашиванием
        output_text = (
            f'Всего сгенерировано: {total_generated}, '
            f'Скорость: {speed:.2f} адр./сек, '
            f'Время работы: {elapsed_time:.2f} секунд, '
            f'Найдено совпадений: {colored(total_found, "green" if total_found > 0 else "red")}'
        )
        print(f'\r{colored(output_text, "cyan")}', end='', flush=True)

# Функция для создания и запуска процессов
def start_worker(worker_id, start_state, progress_dict, rich_addresses, method):
    asyncio.run(check_addresses(worker_id, start_state, progress_dict, rich_addresses, method))

# Основная функция для многопроцессорного запуска
async def main(num_workers, method):
    start_state = await read_state()
    # Загрузка rich адресов в память
    with open(RICH_FILE, 'r') as rich_file:
        rich_addresses = set(line.strip() for line in rich_file)  # Хранение адресов в памяти

    # Общий словарь для хранения прогресса каждого потока
    with Manager() as manager:
        progress_dict = manager.dict({i: (0, 0) for i in range(num_workers)})

        # Запускаем процесс, который будет выводить прогресс
        progress_printer = Process(target=print_progress, args=(progress_dict,))
        progress_printer.start()

        # Запускаем процессы для генерации адресов
        processes = []
        for i in range(num_workers):
            p = Process(target=start_worker, args=(i, start_state, progress_dict, rich_addresses, method))
            processes.append(p)
            p.start()
        for p in processes:
            p.join()  # Ожидаем завершения всех процессов
        progress_printer.join()  # Ожидаем завершения процесса вывода статистики

if __name__ == '__main__':
    # Выводим ASCII-арт только в основном процессе
    ascii_art = pyfiglet.figlet_format("ETH keys generator and checker", font="standard")
    colored_art = colored(ascii_art, 'cyan') 
    print(colored_art)

    # Вывод описания методов генерации с окрашиванием
    description_text = (
        "Выберите метод генерации:\n"
        "1. Высокая энтропия: Генерация приватного ключа с использованием случайных байтов (32 байта).\n"
        "2. Низкая энтропия: Генерация приватного ключа с использованием случайных байтов (16 байт).\n"
    )
    print(colored(description_text, 'cyan'))
    
    # Выбор метода генерации через ввод цифры
    choice = input(colored("Введите номер метода (1 или 2): ", 'cyan')).strip()
    method = 'high' if choice == '1' else 'low' if choice == '2' else 'high'

    # Указываем количество рабочих процессов (по умолчанию 6)
    num_workers = os.cpu_count() or 6

    # Запускаем главную асинхронную функцию
    asyncio.run(main(num_workers, method))
