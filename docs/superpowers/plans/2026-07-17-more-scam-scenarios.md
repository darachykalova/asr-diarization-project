# Больше сценариев мошенничества — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Добавить 8 новых YAML-сценариев мошенничества в `call_agent/scenarios/`, расширив распознавание с 3 до 11 типов звонков.

**Architecture:** Чисто аддитивная правка контента. `load_scenarios()` в `call_agent/scam_detector.py` читает все `*.yaml` из каталога через `glob` — новый файл подхватывается без единой правки Python-кода. Каждый сценарий = один YAML-файл (`key`/`name`/`threshold`/`triggers`) + пара тестов в существующем `tests/call_agent/test_scam_detector.py`.

**Tech Stack:** Python 3.12, PyYAML, pytest. Тесты — чистая логика, без Docker, torch и БД.

## Global Constraints

- **`threshold: 70`** у каждого нового сценария — как у существующих трёх.
- **Нормализация:** `load_scenarios()` прогоняет все `phrases` и `stems` через `_normalize()` (lowercase + `ё`→`е`). В YAML можно писать с `ё` — совпадёт и с `ё`, и с `е` во входящем тексте. Не дублируйте одну фразу в двух написаниях.
- **`phrases` ищутся как точная подстрока** (`p in low`) — «удалённый доступ» НЕ совпадёт с «удалённого доступа». Для словоформ используйте `stems`.
- **`stems` срабатывают, только если ВСЕ корни списка нашлись** среди токенов реплики (`tok.startswith(stem)`), в любом порядке.
- **Одной невинной фразы не должно хватать на порог.** У каждого сценария обязателен тест «похожая невинная фраза остаётся `undetermined`».
- **Не трогать:** существующие `fake_bank.yaml`, `gas_service.yaml`, `police.yaml`, любой Python-код в `call_agent/`, фронтенд.
- **Все 14 существующих тестов должны оставаться зелёными** после каждой задачи. Веса ниже подобраны так, чтобы новые сценарии не перебивали старые — не меняйте их «на глаз».

**Главная ловушка этого плана:** `feed()` начисляет баллы ВСЕМ сценариям, чьи триггеры совпали, а `verdict()` выбирает сценарий с наибольшей уверенностью (`score/threshold`). Поэтому новый сценарий, случайно поймавший чужие слова, может перехватить вердикт у `fake_bank` и сломать `test_real_call_2026_07_13_regression`. Отдельно опасен `test_case_insensitive_and_delta`: он суммирует веса хитов по ВСЕМ сценариям и жёстко ждёт `65`.

---

### Task 1: Сценарий «родственник в беде»

**Files:**
- Create: `call_agent/scenarios/relative_in_trouble.yaml`
- Modify: `tests/call_agent/test_scam_detector.py` (переименовать `test_loads_three_scenarios`, добавить 2 теста)

**Interfaces:**
- Consumes: `load_scenarios(dir)` и `ScamDetector` из `call_agent/scam_detector.py` (уже существуют, не меняются). Хелпер `_detector()` уже есть в тест-файле.
- Produces: ключ сценария `relative_in_trouble`; тест `test_loads_scenarios` (переименован из `test_loads_three_scenarios`) — все последующие задачи дописывают в его набор свой ключ.

- [ ] **Step 1: Написать падающие тесты**

В `tests/call_agent/test_scam_detector.py` заменить существующий тест:

```python
def test_loads_three_scenarios():
    scenarios = load_scenarios(SCEN_DIR)
    keys = {s.key for s in scenarios}
    assert keys == {"fake_bank", "gas_service", "police"}
```

на:

```python
def test_loads_scenarios():
    scenarios = load_scenarios(SCEN_DIR)
    keys = {s.key for s in scenarios}
    assert keys == {
        "fake_bank", "gas_service", "police",
        "relative_in_trouble",
    }
```

И добавить в конец файла:

```python
def test_relative_in_trouble_crosses_threshold():
    d = _detector()
    d.feed("мама это я попал в аварию")          # 45 + 45 = 90
    verdict, scenario, conf = d.verdict()
    assert verdict == "scam"
    assert scenario == "relative_in_trouble"


def test_innocent_family_call_stays_undetermined():
    d = _detector()
    d.feed("привет мама это я как твои дела")     # 45 < 70
    assert d.verdict()[0] == "undetermined"
```

- [ ] **Step 2: Запустить тесты — убедиться, что падают**

Run: `python -m pytest tests/call_agent/test_scam_detector.py -q`
Expected: FAIL — `test_loads_scenarios` (в наборе нет `relative_in_trouble`) и `test_relative_in_trouble_crosses_threshold` (вердикт `undetermined`).

- [ ] **Step 3: Создать YAML-сценарий**

Создать `call_agent/scenarios/relative_in_trouble.yaml`:

```yaml
key: relative_in_trouble
name: Родственник в беде
threshold: 70
triggers:
  - phrases: ["мама это я", "папа это я", "бабушка это я", "это твой внук", "это твой сын"]
    weight: 45
  - phrases: ["попал в аварию", "попала в аварию", "сбил человека", "меня задержали"]
    weight: 45
  - phrases: ["никому не говори", "только не говори маме", "не говори папе"]
    weight: 35
  - stems: ["авари", "деньг"]
    weight: 55
  - stems: ["адвокат", "деньг"]
    weight: 55
  - stems: ["сроч", "перевед"]
    weight: 50
```

- [ ] **Step 4: Запустить весь файл тестов — всё зелёное**

Run: `python -m pytest tests/call_agent/test_scam_detector.py -q`
Expected: PASS, 16 passed (14 исходных, из которых один переименован, + 2 новых).

Если упал какой-то из **старых** тестов — новый сценарий поймал чужие слова. Не правьте старый тест: сузьте триггер нового сценария.

- [ ] **Step 5: Коммит**

```bash
git add call_agent/scenarios/relative_in_trouble.yaml tests/call_agent/test_scam_detector.py
git commit -m "feat(call-agent): detect relative-in-trouble scam scenario"
```

---

### Task 2: Сценарий «мобильный оператор»

**Files:**
- Create: `call_agent/scenarios/mobile_operator.yaml`
- Modify: `tests/call_agent/test_scam_detector.py`

**Interfaces:**
- Consumes: `test_loads_scenarios` из Task 1 — дописать в его набор ключ.
- Produces: ключ сценария `mobile_operator`.

**Осторожно:** `fake_bank` ловит фразу «карта заблокирована». Здесь НЕЛЬЗЯ использовать голый корень `заблокир` — иначе `test_bank_scam_crosses_threshold` может отдать вердикт этому сценарию. Используются только точные фразы про номер.

- [ ] **Step 1: Написать падающие тесты**

Обновить набор ключей в `test_loads_scenarios`:

```python
def test_loads_scenarios():
    scenarios = load_scenarios(SCEN_DIR)
    keys = {s.key for s in scenarios}
    assert keys == {
        "fake_bank", "gas_service", "police",
        "relative_in_trouble", "mobile_operator",
    }
```

Добавить в конец файла:

```python
def test_mobile_operator_crosses_threshold():
    d = _detector()
    d.feed("ваш номер будет заблокирован завтра")   # 45
    d.feed("нужен перевыпуск сим-карты")             # 45 + 40 = 85
    verdict, scenario, conf = d.verdict()
    assert verdict == "scam"
    assert scenario == "mobile_operator"


def test_innocent_simcard_talk_stays_undetermined():
    d = _detector()
    d.feed("я купил новую сим-карту вчера")          # 40 < 70
    assert d.verdict()[0] == "undetermined"
```

- [ ] **Step 2: Запустить тесты — убедиться, что падают**

Run: `python -m pytest tests/call_agent/test_scam_detector.py -q`
Expected: FAIL — `test_loads_scenarios` и `test_mobile_operator_crosses_threshold`.

- [ ] **Step 3: Создать YAML-сценарий**

Создать `call_agent/scenarios/mobile_operator.yaml`:

```yaml
key: mobile_operator
name: Мобильный оператор
threshold: 70
triggers:
  - phrases: ["номер будет заблокирован", "ваш номер заблокируют", "договор на ваш номер истекает"]
    weight: 45
  - phrases: ["перевыпуск сим-карты", "замена сим-карты", "переоформление номера"]
    weight: 45
  - stems: ["сим", "карт"]
    weight: 40
  - stems: ["продлен", "номер"]
    weight: 40
```

- [ ] **Step 4: Запустить весь файл тестов — всё зелёное**

Run: `python -m pytest tests/call_agent/test_scam_detector.py -q`
Expected: PASS. Особое внимание: `test_bank_scam_crosses_threshold` должен по-прежнему возвращать `scenario == "fake_bank"`.

- [ ] **Step 5: Коммит**

```bash
git add call_agent/scenarios/mobile_operator.yaml tests/call_agent/test_scam_detector.py
git commit -m "feat(call-agent): detect mobile operator scam scenario"
```

---

### Task 3: Сценарий «техподдержка / вирус»

**Files:**
- Create: `call_agent/scenarios/tech_support.yaml`
- Modify: `tests/call_agent/test_scam_detector.py`

**Interfaces:**
- Consumes: `test_loads_scenarios` из Task 2 — дописать в его набор ключ.
- Produces: ключ сценария `tech_support`.

**Осторожно:** «удалённый доступ» как `phrases` не поймает «удалённого доступа» (подстрочное сравнение) — поэтому здесь `stems: ["удален", "доступ"]`.

- [ ] **Step 1: Написать падающие тесты**

Обновить набор ключей в `test_loads_scenarios`:

```python
def test_loads_scenarios():
    scenarios = load_scenarios(SCEN_DIR)
    keys = {s.key for s in scenarios}
    assert keys == {
        "fake_bank", "gas_service", "police",
        "relative_in_trouble", "mobile_operator", "tech_support",
    }
```

Добавить в конец файла:

```python
def test_tech_support_crosses_threshold():
    d = _detector()
    d.feed("у вас вирус на компьютере")                   # 40
    d.feed("установите программу удалённого доступа")      # 50 + 40 = 90
    verdict, scenario, conf = d.verdict()
    assert verdict == "scam"
    assert scenario == "tech_support"


def test_innocent_software_talk_stays_undetermined():
    d = _detector()
    d.feed("установи мне программу для монтажа видео")     # 40 < 70
    assert d.verdict()[0] == "undetermined"
```

- [ ] **Step 2: Запустить тесты — убедиться, что падают**

Run: `python -m pytest tests/call_agent/test_scam_detector.py -q`
Expected: FAIL — `test_loads_scenarios` и `test_tech_support_crosses_threshold`.

- [ ] **Step 3: Создать YAML-сценарий**

Создать `call_agent/scenarios/tech_support.yaml`:

```yaml
key: tech_support
name: Техподдержка / вирус на компьютере
threshold: 70
triggers:
  - phrases: ["вирус на компьютере", "компьютер заражён", "заражён вирусом", "компьютер взломали"]
    weight: 40
  - phrases: ["anydesk", "teamviewer"]
    weight: 50
  - phrases: ["техническая поддержка", "техподдержка", "служба поддержки"]
    weight: 30
  - stems: ["удален", "доступ"]
    weight: 50
  - stems: ["установ", "программ"]
    weight: 40
  - stems: ["скача", "программ"]
    weight: 40
```

- [ ] **Step 4: Запустить весь файл тестов — всё зелёное**

Run: `python -m pytest tests/call_agent/test_scam_detector.py -q`
Expected: PASS.

- [ ] **Step 5: Коммит**

```bash
git add call_agent/scenarios/tech_support.yaml tests/call_agent/test_scam_detector.py
git commit -m "feat(call-agent): detect tech support scam scenario"
```

---

### Task 4: Сценарий «Госуслуги / соцвыплата»

**Files:**
- Create: `call_agent/scenarios/gosuslugi.yaml`
- Modify: `tests/call_agent/test_scam_detector.py`

**Interfaces:**
- Consumes: `test_loads_scenarios` из Task 3 — дописать в его набор ключ.
- Produces: ключ сценария `gosuslugi`.

**Осторожно:** пара `["код", "смс"]` принадлежит `fake_bank` (вес 60) — здесь её дублировать НЕЛЬЗЯ, иначе `test_real_call_2026_07_13_regression` рискует отдать вердикт не тому сценарию. Здесь код привязан к слову «госуслуги»: `["код", "госуслуг"]`.

- [ ] **Step 1: Написать падающие тесты**

Обновить набор ключей в `test_loads_scenarios`:

```python
def test_loads_scenarios():
    scenarios = load_scenarios(SCEN_DIR)
    keys = {s.key for s in scenarios}
    assert keys == {
        "fake_bank", "gas_service", "police",
        "relative_in_trouble", "mobile_operator", "tech_support",
        "gosuslugi",
    }
```

Добавить в конец файла:

```python
def test_gosuslugi_crosses_threshold():
    d = _detector()
    d.feed("вам звонят с портала госуслуг")                 # 40
    d.feed("продиктуйте код подтверждения от госуслуг")      # 40 + 60 = 100
    verdict, scenario, conf = d.verdict()
    assert verdict == "scam"
    assert scenario == "gosuslugi"


def test_innocent_gosuslugi_mention_stays_undetermined():
    d = _detector()
    d.feed("я вчера зашёл на госуслуги и записался к врачу")  # 40 < 70
    assert d.verdict()[0] == "undetermined"
```

- [ ] **Step 2: Запустить тесты — убедиться, что падают**

Run: `python -m pytest tests/call_agent/test_scam_detector.py -q`
Expected: FAIL — `test_loads_scenarios` и `test_gosuslugi_crosses_threshold`.

- [ ] **Step 3: Создать YAML-сценарий**

Создать `call_agent/scenarios/gosuslugi.yaml`:

```yaml
key: gosuslugi
name: Госуслуги / соцвыплата
threshold: 70
triggers:
  - stems: ["госуслуг"]
    weight: 40
  - phrases: ["аккаунт взломан", "взломали ваш аккаунт", "личный кабинет взломали"]
    weight: 40
  - phrases: ["социальная выплата", "единовременная выплата", "положена выплата", "перерасчёт пенсии"]
    weight: 40
  - stems: ["код", "госуслуг"]
    weight: 60
  - stems: ["выплат", "код"]
    weight: 50
```

- [ ] **Step 4: Запустить весь файл тестов — всё зелёное**

Run: `python -m pytest tests/call_agent/test_scam_detector.py -q`
Expected: PASS. Особое внимание: `test_real_call_2026_07_13_regression` и `test_single_strong_phrase_enough` должны остаться зелёными.

- [ ] **Step 5: Коммит**

```bash
git add call_agent/scenarios/gosuslugi.yaml tests/call_agent/test_scam_detector.py
git commit -m "feat(call-agent): detect gosuslugi scam scenario"
```

---

### Task 5: Сценарий «почта / доставка»

**Files:**
- Create: `call_agent/scenarios/delivery.yaml`
- Modify: `tests/call_agent/test_scam_detector.py`

**Interfaces:**
- Consumes: `test_loads_scenarios` из Task 4 — дописать в его набор ключ.
- Produces: ключ сценария `delivery`.

**Осторожно:** пара `["код", "получен"]` намеренно НЕ используется — настоящие курьеры тоже просят код получения, это дало бы ложные срабатывания.

- [ ] **Step 1: Написать падающие тесты**

Обновить набор ключей в `test_loads_scenarios`:

```python
def test_loads_scenarios():
    scenarios = load_scenarios(SCEN_DIR)
    keys = {s.key for s in scenarios}
    assert keys == {
        "fake_bank", "gas_service", "police",
        "relative_in_trouble", "mobile_operator", "tech_support",
        "gosuslugi", "delivery",
    }
```

Добавить в конец файла:

```python
def test_delivery_crosses_threshold():
    d = _detector()
    d.feed("ваша посылка задержана на таможне")   # 25 + 40 = 65
    d.feed("нужно оплатить пошлину")               # 50 -> 115
    verdict, scenario, conf = d.verdict()
    assert verdict == "scam"
    assert scenario == "delivery"


def test_innocent_parcel_talk_stays_undetermined():
    d = _detector()
    d.feed("посылка придёт завтра курьером")       # 25 < 70
    assert d.verdict()[0] == "undetermined"
```

- [ ] **Step 2: Запустить тесты — убедиться, что падают**

Run: `python -m pytest tests/call_agent/test_scam_detector.py -q`
Expected: FAIL — `test_loads_scenarios` и `test_delivery_crosses_threshold`.

- [ ] **Step 3: Создать YAML-сценарий**

Создать `call_agent/scenarios/delivery.yaml`:

```yaml
key: delivery
name: Почта / служба доставки
threshold: 70
triggers:
  - stems: ["посылк"]
    weight: 25
  - phrases: ["застряла на таможне", "задержана на таможне", "таможенный сбор"]
    weight: 40
  - stems: ["пошлин", "оплат"]
    weight: 50
  - stems: ["код", "курьер"]
    weight: 60
  - phrases: ["оплатите доставку", "доплатить за доставку"]
    weight: 35
```

- [ ] **Step 4: Запустить весь файл тестов — всё зелёное**

Run: `python -m pytest tests/call_agent/test_scam_detector.py -q`
Expected: PASS. Особое внимание: `test_innocent_code_mention_stays_undetermined` должен остаться зелёным.

- [ ] **Step 5: Коммит**

```bash
git add call_agent/scenarios/delivery.yaml tests/call_agent/test_scam_detector.py
git commit -m "feat(call-agent): detect delivery scam scenario"
```

---

### Task 6: Сценарий «брокер / инвестиции»

**Files:**
- Create: `call_agent/scenarios/broker_investment.yaml`
- Modify: `tests/call_agent/test_scam_detector.py`

**Interfaces:**
- Consumes: `test_loads_scenarios` из Task 5 — дописать в его набор ключ.
- Produces: ключ сценария `broker_investment`.

**Осторожно:** пара `["брокерск", "счет"]` намеренно НЕ используется — фраза «я открыл брокерский счёт» абсолютно легальна и давала бы ложное срабатывание. Голый корень `["брокер"]` весит 35 — сам по себе порога не даёт.

- [ ] **Step 1: Написать падающие тесты**

Обновить набор ключей в `test_loads_scenarios`:

```python
def test_loads_scenarios():
    scenarios = load_scenarios(SCEN_DIR)
    keys = {s.key for s in scenarios}
    assert keys == {
        "fake_bank", "gas_service", "police",
        "relative_in_trouble", "mobile_operator", "tech_support",
        "gosuslugi", "delivery", "broker_investment",
    }
```

Добавить в конец файла:

```python
def test_broker_investment_crosses_threshold():
    d = _detector()
    d.feed("здравствуйте я ваш личный консультант")     # 40
    d.feed("гарантированный доход на инвестициях")       # 45 + 45 = 90
    verdict, scenario, conf = d.verdict()
    assert verdict == "scam"
    assert scenario == "broker_investment"


def test_innocent_broker_account_stays_undetermined():
    d = _detector()
    d.feed("я открыл брокерский счёт в прошлом году")    # 35 < 70
    assert d.verdict()[0] == "undetermined"
```

- [ ] **Step 2: Запустить тесты — убедиться, что падают**

Run: `python -m pytest tests/call_agent/test_scam_detector.py -q`
Expected: FAIL — `test_loads_scenarios` и `test_broker_investment_crosses_threshold`.

- [ ] **Step 3: Создать YAML-сценарий**

Создать `call_agent/scenarios/broker_investment.yaml`:

```yaml
key: broker_investment
name: Брокер / инвестиции
threshold: 70
triggers:
  - phrases: ["заработок на бирже", "инвестиционная платформа", "личный консультант", "финансовый консультант"]
    weight: 40
  - stems: ["брокер"]
    weight: 35
  - stems: ["инвестиц", "доход"]
    weight: 45
  - stems: ["крипт", "вложи"]
    weight: 50
  - phrases: ["гарантированная доходность", "гарантированный доход", "без риска"]
    weight: 45
```

- [ ] **Step 4: Запустить весь файл тестов — всё зелёное**

Run: `python -m pytest tests/call_agent/test_scam_detector.py -q`
Expected: PASS.

- [ ] **Step 5: Коммит**

```bash
git add call_agent/scenarios/broker_investment.yaml tests/call_agent/test_scam_detector.py
git commit -m "feat(call-agent): detect broker/investment scam scenario"
```

---

### Task 7: Сценарий «лотерея / выигрыш приза»

**Files:**
- Create: `call_agent/scenarios/lottery.yaml`
- Modify: `tests/call_agent/test_scam_detector.py`

**Interfaces:**
- Consumes: `test_loads_scenarios` из Task 6 — дописать в его набор ключ.
- Produces: ключ сценария `lottery`.

- [ ] **Step 1: Написать падающие тесты**

Обновить набор ключей в `test_loads_scenarios`:

```python
def test_loads_scenarios():
    scenarios = load_scenarios(SCEN_DIR)
    keys = {s.key for s in scenarios}
    assert keys == {
        "fake_bank", "gas_service", "police",
        "relative_in_trouble", "mobile_operator", "tech_support",
        "gosuslugi", "delivery", "broker_investment", "lottery",
    }
```

Добавить в конец файла:

```python
def test_lottery_crosses_threshold():
    d = _detector()
    d.feed("поздравляем вы выиграли приз в лотерее")   # 45 + 50 + 30 = 125
    verdict, scenario, conf = d.verdict()
    assert verdict == "scam"
    assert scenario == "lottery"


def test_innocent_lottery_talk_stays_undetermined():
    d = _detector()
    d.feed("мы вчера играли в лотерею с друзьями")     # 30 < 70
    assert d.verdict()[0] == "undetermined"
```

- [ ] **Step 2: Запустить тесты — убедиться, что падают**

Run: `python -m pytest tests/call_agent/test_scam_detector.py -q`
Expected: FAIL — `test_loads_scenarios` и `test_lottery_crosses_threshold`.

- [ ] **Step 3: Создать YAML-сценарий**

Создать `call_agent/scenarios/lottery.yaml`:

```yaml
key: lottery
name: Лотерея / выигрыш приза
threshold: 70
triggers:
  - phrases: ["вы выиграли", "вы стали победителем", "ваш номер выиграл", "розыгрыш призов"]
    weight: 45
  - stems: ["выигр", "приз"]
    weight: 50
  - stems: ["налог", "выигрыш"]
    weight: 55
  - phrases: ["оплатите доставку приза", "организационный сбор"]
    weight: 45
  - stems: ["лотере"]
    weight: 30
```

- [ ] **Step 4: Запустить весь файл тестов — всё зелёное**

Run: `python -m pytest tests/call_agent/test_scam_detector.py -q`
Expected: PASS.

- [ ] **Step 5: Коммит**

```bash
git add call_agent/scenarios/lottery.yaml tests/call_agent/test_scam_detector.py
git commit -m "feat(call-agent): detect lottery scam scenario"
```

---

### Task 8: Сценарий «работодатель / фальшивая вакансия» + финальная проверка

**Files:**
- Create: `call_agent/scenarios/fake_employer.yaml`
- Modify: `tests/call_agent/test_scam_detector.py`

**Interfaces:**
- Consumes: `test_loads_scenarios` из Task 7 — дописать в его набор последний ключ (итого 11).
- Produces: ключ сценария `fake_employer`. Финальное состояние: 11 сценариев.

**Осторожно:** фраза «удалённая работа» пересекается по корню `удален` с `tech_support` (`["удален", "доступ"]`), но там требуется ещё и корень `доступ` — конфликта нет.

- [ ] **Step 1: Написать падающие тесты**

Обновить набор ключей в `test_loads_scenarios` до финальных 11:

```python
def test_loads_scenarios():
    scenarios = load_scenarios(SCEN_DIR)
    keys = {s.key for s in scenarios}
    assert keys == {
        "fake_bank", "gas_service", "police",
        "relative_in_trouble", "mobile_operator", "tech_support",
        "gosuslugi", "delivery", "broker_investment", "lottery",
        "fake_employer",
    }
```

Добавить в конец файла:

```python
def test_fake_employer_crosses_threshold():
    d = _detector()
    d.feed("у нас есть вакансия удалённая работа")      # 25 + 35 = 60
    d.feed("нужно оплатить обучение перед стартом")      # 50 + 40 = 90
    verdict, scenario, conf = d.verdict()
    assert verdict == "scam"
    assert scenario == "fake_employer"


def test_innocent_job_talk_stays_undetermined():
    d = _detector()
    d.feed("я нашла вакансию удалённая работа в такси")  # 25 + 35 = 60 < 70
    assert d.verdict()[0] == "undetermined"
```

- [ ] **Step 2: Запустить тесты — убедиться, что падают**

Run: `python -m pytest tests/call_agent/test_scam_detector.py -q`
Expected: FAIL — `test_loads_scenarios` и `test_fake_employer_crosses_threshold`.

- [ ] **Step 3: Создать YAML-сценарий**

Создать `call_agent/scenarios/fake_employer.yaml`:

```yaml
key: fake_employer
name: Работодатель / фальшивая вакансия
threshold: 70
triggers:
  - phrases: ["удалённая работа", "подработка на дому", "вакансия для вас"]
    weight: 35
  - stems: ["вакан"]
    weight: 25
  - stems: ["оплат", "обучени"]
    weight: 50
  - stems: ["депозит"]
    weight: 40
  - stems: ["взнос", "материал"]
    weight: 45
  - phrases: ["первый взнос", "стартовый взнос", "оплатить обучение"]
    weight: 40
```

- [ ] **Step 4: Запустить весь файл тестов — всё зелёное**

Run: `python -m pytest tests/call_agent/test_scam_detector.py -q`
Expected: PASS, 30 passed (14 исходных + 16 новых).

- [ ] **Step 5: Прогнать весь тест-сьют проекта**

Run: `python -m pytest tests/ -m "not requires_torch and not requires_db" -q`
Expected: PASS — ни один тест вне детектора не должен сломаться (сценарии нигде больше не захардкожены; проверяем это фактом, а не предположением).

- [ ] **Step 6: Коммит**

```bash
git add call_agent/scenarios/fake_employer.yaml tests/call_agent/test_scam_detector.py
git commit -m "feat(call-agent): detect fake employer scam scenario"
```

---

## Проверка результата

После всех 8 задач:

```bash
ls call_agent/scenarios/     # 11 файлов
python -m pytest tests/call_agent/test_scam_detector.py -q   # 30 passed
```

Пересборка контейнера для живой работы (сценарии запекаются в образ через `COPY`, рестарта недостаточно):

```bash
docker compose build api && docker compose build call-agent && docker compose up -d call-agent
```

## Вне рамок

- Живой тест новых сценариев в браузерном симуляторе — отдельная задача.
- Реплики агента под конкретный сценарий (сейчас `keep_talking`/`before_hangup` общие) — не делаем.
- Изменение весов/триггеров существующих `fake_bank`/`gas_service`/`police` — не трогаем.
