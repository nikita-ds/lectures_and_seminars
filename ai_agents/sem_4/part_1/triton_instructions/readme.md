В этой заметке содержится инструкция и пути решения некоторых проблем, с которыми вы можете столкнуться, если будете разворачивать vllm + triton на windows/linux

```
используемая версия docker: 28.1.1
ожидаемая структура папок:

triton_project/
└── model_repository/
    └── gemma/
        ├── config.pbtxt (есть в примерах)
        └── 1/
            └── model.json (есть в примерах)
    
```
на этом [сайте](https://catalog.ngc.nvidia.com/orgs/nvidia/containers/tritonserver/tags) находим актуальную версию docker образа и скачиваем ее
```
docker pull nvcr.io/nvidia/tritonserver:25.06-vllm-python-py3
```

### Разбор команды docker для запуска Triton + vLLM

Финальная команда для запуска Triton состоит из множества флагов. Необходимо понимать, за что отвечает каждый из них, чтобы уверенно использовать и адаптировать команду под свои нужды.

**Команда для запуска:**
```powershell
docker run --gpus all -d --rm -p 8000:8000 -p 8001:8001 -p 8002:8002 --env HUGGING_FACE_HUB_TOKEN=$env:HF_TOKEN --mount type=bind,source="C:\Users\<ваше_имя_пользователя>\triton_project\model_repository",target="/models" --mount type=volume,source=triton_hf_cache,target="/root/.cache/huggingface" --name triton_vllm_server nvcr.io/nvidia/tritonserver:25.06-vllm-python-py3 tritonserver --model-repository=/models --model-control-mode=explicit --load-model=gemma
```


**Покомпонентный разбор команды:**

#### **Часть 1: Управление ресурсами и поведением Docker**

*   `docker run`
    *   **Что делает:** Основная команда Docker для создания и запуска нового контейнера.

*   `--gpus all`
    *   **Что делает:** Предоставляет контейнеру доступ ко всем доступным графическим процессорам (GPU) на вашем компьютере. Это **обязательно** для работы vLLM.

*   `-d`
    *   **Что делает:** Сокращение от `--detach`. Запускает контейнер в **фоновом режиме**. Вы не будете видеть логи в реальном времени, но получите обратно управление терминалом.

*   `--rm`
    *   **Что делает:** Автоматически **удаляет контейнер** после его остановки. Это хорошая практика для чистоты системы, так как остановленные контейнеры не будут накапливаться.

*   `-p 8000:8000 -p 8001:8001 -p 8002:8002`
    *   **Что делает:** "Пробрасывает" порты с вашего компьютера (хоста) внутрь контейнера.
        *   `8000`: порт для HTTP-запросов.
        *   `8001`: порт для gRPC-запросов.
        *   `8002`: порт для метрик Prometheus.
    *   **Зачем нужно:** Чтобы вы могли отправлять запросы на `localhost:8000` и попадать в Triton-сервер внутри контейнера.

#### **Часть 2: Настройка среды и данных контейнера**

*   `--env HUGGING_FACE_HUB_TOKEN=$env:HF_TOKEN`
    *   **Что делает:** Создает **переменную окружения** `HUGGING_FACE_HUB_TOKEN` внутри контейнера.
    *   **Зачем нужно:** vLLM автоматически ищет эту переменную, чтобы получить ваш токен доступа и скачать "защищенные" модели (такие как Gemma) с Hugging Face. `$env:HF_TOKEN` — это синтаксис PowerShell для получения значения локальной переменной.

*   `--mount type=bind,source="C:\... \model_repository",target="/models"`
    *   **Что делает:** **Связывает (bind)** вашу локальную папку `model_repository` с папкой `/models` внутри контейнера.
    *   **Зачем нужно:** Это позволяет Triton найти ваш `config.pbtxt` и `model.json`. Вы можете редактировать эти файлы на своем компьютере, и изменения будут мгновенно видны серверу после перезапуска.

*   `--mount type=volume,source=triton_hf_cache,target="/root/.cache/huggingface"`
    *   **Что делает:** Монтирует **именованный том (volume)** Docker по имени `triton_hf_cache` в папку, где Hugging Face хранит кэш скачанных моделей.
    *   **Зачем нужно:** Это самый производительный способ хранения данных. Скачанные веса модели (несколько гигабайт) будут сохранены в этом томе. При следующем запуске контейнера модель не будет скачиваться заново, а будет мгновенно взята из кэша.

*   `--name triton_vllm_server`
    *   **Что делает:** Присваивает контейнеру легко запоминаемое имя.
    *   **Зачем нужно:** Чтобы вы могли обращаться к контейнеру по имени (`docker logs triton_vllm_server`, `docker stop triton_vllm_server`), а не по его длинному ID.

#### **Часть 3: Запуск самого Triton Server и его конфигурация**

*   `nvcr.io/nvidia/tritonserver:25.06-vllm-python-py3`
    *   **Что делает:** Указывает Docker, какой **образ** использовать для создания контейнера. Это официальный образ от NVIDIA, содержащий Triton Server и уже установленный vLLM бэкенд.

*   `tritonserver ...` (все, что идет после имени образа)
    *   **Что делает:** Это **команда, которая выполняется внутри контейнера** при его старте. Мы запускаем сам исполняемый файл `tritonserver` и передаем ему флаги.

*   `--model-repository=/models`
    *   **Что делает:** Указывает Triton, в какой папке внутри контейнера искать модели. Это соответствует `target` из нашего `--mount` флага.

*   `--model-control-mode=explicit`
    *   **Что делает:** Переключает Triton в режим явного управления моделями. Он перестает автоматически сканировать папку `/models`.

*   `--load-model=gemma`
    *   **Что делает:** Приказывает Triton принудительно загрузить модель с именем `gemma` при старте.
    *   **Зачем нужны два последних флага:** Эта комбинация заставляет Triton работать в режиме постоянного сервиса, а не выключаться после проверки конфигурации.


### Диагностика монтирования папок: тест с Ubuntu для исправления `path does not exist`

**Проблема:**
Даже с правильным синтаксисом `--mount`, Docker выдает ошибку, что путь не существует, и вы не уверены, какой именно формат пути (`C:\...` или `/mnt/c/...`) использовать.
```
docker: Error response from daemon: invalid mount config for type "bind": bind source path does not exist...
```

**Почему это происходит?**
Проблема может быть как в формате пути, так и в конфигурации самого Docker Desktop. Нужно провести простой тест, чтобы изолировать проблему от сложной команды запуска Triton.

**Решение:**
Запустить минималистичный контейнер `ubuntu` и попытаться примонтировать только одну папку, используя стандартный путь Windows. Это покажет, работает ли базовый функционал Docker.

**Конкретный пример:**

1.  **Выполните тестовую команду в PowerShell:**
    ```powershell
    docker run --rm --mount type=bind,source="C:\Users\<ваше_имя_пользователя_windows>\triton_project\model_repository",target="/data" ubuntu ls -l /data
    ```
2.  **Проанализируйте результат:**
    *   **Успех (вывелся список файлов):** Вы увидите содержимое вашей папки `model_repository`. Это доказывает, что синтаксис `source="C:\..."` **правильный**. Используйте его в вашей основной команде для запуска Triton.
    *   **Провал (та же ошибка):** Проблема в самой установке Docker. Сбросьте Docker Desktop до заводских настроек через `Settings -> Troubleshoot -> Reset to factory defaults`.


### Отладка контейнера Triton, который сразу останавливается

**Проблема:**
Вы запускаете `docker run -d ...`, команда не выдает ошибок, но контейнер не появляется в списке `docker ps`.

**Почему это происходит?**
Контейнер запускается, но процесс `tritonserver` внутри него падает из-за ошибки. Флаг `--rm` в вашей команде немедленно удаляет остановленный контейнер, не давая вам посмотреть логи.

**Решение:**
Временно убрать флаг `--rm`, чтобы "поймать" упавший контейнер и прочитать его логи.

**Конкретный пример:**

1.  **Измените команду запуска, удалив `--rm`:**
    ```powershell
    # Обратите внимание, что --rm отсутствует
    docker run -d `
        --gpus all `
        --name triton_vllm_server `
        ... # остальные флаги
    ```
2.  **Запустите команду.**
3.  **Найдите остановленный контейнер:**
    ```powershell
    # Флаг -a показывает все контейнеры, включая остановленные
    docker ps -a
    # В выводе вы увидите ваш контейнер со статусом "Exited"
    ```
4.  **Прочитайте логи, чтобы найти ошибку:**
    ```powershell
    docker logs triton_vllm_server
    ```

### Правильная настройка репозитория моделей для Triton с vLLM

**Проблема:**
Triton находит модель, но не может ее загрузить, выдавая ошибки:
*   `AssertionError: 'model.json' containing vllm engine args must be provided...`
*   `TypeError: AsyncEngineArgs.__init__() got an unexpected keyword argument 'engine_args'`

**Почему это происходит?**
Современный vLLM бэкенд требует разделения конфигурации:
*   `config.pbtxt`: для общих настроек Triton (имя, входы/выходы).
*   `model.json`: для специфичных параметров движка vLLM (имя модели, использование GPU).

**Решение:**
Создать правильную структуру папок и распределить параметры по двум файлам.

**Конкретный пример:**

1.  **Структура папок:**
    ```
    model_repository/
    └── gemma/
        ├── config.pbtxt
        └── 1/
            └── model.json
    ```
2.  **Содержимое `config.pbtxt` (в папке `gemma/`):**
    ```pbtxt
    name: "gemma"
    backend: "vllm"
    max_batch_size: 256
    model_transaction_policy { decoupled: true }
    input [ { name: "text_input", data_type: TYPE_STRING, dims: [ -1 ] } ] # и другие inputs/outputs
    output [ { name: "text_output", data_type: TYPE_STRING, dims: [ -1 ] } ]
    ```
3.  **Содержимое `model.json` (в папке `gemma/1/`):**
    ```json
    {
      "model": "google/gemma-2b-it",
      "tensor_parallel_size": 1,
      "gpu_memory_utilization": 0.90
    }
    ```


### Использование защищенных моделей Hugging Face (Gemma) в Triton

**Проблема:**
Процесс загрузки модели прерывается с ошибкой `401 Client Error` или сообщением `You are trying to access a gated repo`.

**Почему это происходит?**
Модели Google Gemma требуют, чтобы вы приняли их условия использования на сайте Hugging Face. Ваш токен доступа подтверждает вашу личность и согласие.

**Решение:**
Принять условия и передать ваш токен Hugging Face внутрь Docker-контейнера.

**Конкретный пример:**

1.  **На сайте Hugging Face:** Перейдите на страницу модели, например, `google/gemma-2b-it`, и нажмите "Agree and access repository".
2.  **В вашем профиле Hugging Face:** Создайте токен доступа в `Settings -> Access Tokens`. (https://huggingface.co/settings/tokens)
3.  **В терминале PowerShell:** Установите токен как переменную окружения:
    ```powershell
    $env:HF_TOKEN="hf_ВАШ_ДЛИННЫЙ_ТОКЕН_ДОСТУПА"
    ```
4.  **В команде `docker run`:** Добавьте флаг `--env`, чтобы передать токен внутрь контейнера:
    ```powershell
    docker run `
        --gpus all `
        -d --rm `
        --env HUGGING_FACE_HUB_TOKEN=$env:HF_TOKEN `
        ... # остальные флаги
    ```


### Как заставить Triton Server работать постоянно и не выключаться после загрузки

**Проблема:**
В логах вы видите, что модель успешно загрузилась и получила статус `READY`, но сразу после этого сервер начинает процедуру выгрузки модели и завершает работу.

**Почему это происходит?**
По умолчанию Triton может запуститься в режиме "проверки конфигурации". Он проверяет, что может загрузить модели, отчитывается об успехе и завершает работу. Чтобы он работал как сервис, ему нужно явно приказать это сделать.

**Решение:**
Использовать флаги `--model-control-mode=explicit` и `--load-model` для переключения в режим постоянной работы.

**Конкретный пример:**

*   **Команда, которая может выключаться:**
    ```
    ... nvcr.io/nvidia/tritonserver:25.06-vllm-python-py3 tritonserver --model-repository=/models
    ```
*   **Правильная команда для постоянной работы:**
    ```
    ... nvcr.io/nvidia/tritonserver:25.06-vllm-python-py3 tritonserver --model-repository=/models --model-control-mode=explicit --load-model=gemma
    ```


### Отправка запросов на работающий Triton/vLLM сервер через Python

**Проблема:**
Сервер запущен, модель `gemma` имеет статус `READY`. Как отправить ей промпт и получить ответ?

**Решение:**
Использовать библиотеку Python `requests` для отправки POST-запроса на специальный стриминговый эндпоинт Triton.

**Конкретный пример:**

1.  **Установите библиотеку:** `pip install requests`
2.  **Создайте и запустите Python-скрипт:**
    ```python
    import requests
    import json

    # Эндпоинт для стриминга модели gemma
    url = "http://localhost:8000/v2/models/gemma/generate_stream"

    # Параметры для генерации
    sampling_parameters = {
        "max_tokens": 256,
        "temperature": 0.7
    }

    # Тело запроса, соответствующее inputs в config.pbtxt
    payload = {
        "text_input": "Расскажи в трех предложениях, почему небо голубое.",
        "stream": True,
        "sampling_parameters": json.dumps(sampling_parameters)
    }

    print("Отправляем запрос...")
    try:
        # Отправляем запрос и обрабатываем потоковый ответ
        with requests.post(url, json=payload, stream=True) as response:
            response.raise_for_status()
            print("Ответ модели: ", end="")
            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8')
                    if decoded_line.startswith("data: "):
                        content = decoded_line[len("data: "):]
                        if content == "[DONE]":
                            break
                        # Извлекаем и печатаем текст
                        text_output = json.loads(content).get("text_output", "")
                        print(text_output, end="", flush=True)
        print("\nГенерация завершена.")
    except requests.exceptions.RequestException as e:
        print(f"\nОшибка подключения к серверу: {e}")
    ```