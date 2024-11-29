from flask import Flask, render_template, jsonify
import RPi.GPIO as gpio
import time as delay
from urllib.request import urlopen
import requests  # Para usar o requests.post
from app import app


# Configuração do GPIO
gpio.setmode(gpio.BOARD)
gpio.setwarnings(False)

# Pinos dos LEDs
ledVermelho, ledVerde = 11, 12

# Pinos do Sensor Ultrassônico
pin_t = 15  # Trigger
pin_e = 16  # Echo
lixeira_v = 20

# Configuração dos pinos
gpio.setup(ledVermelho, gpio.OUT)
gpio.setup(ledVerde, gpio.OUT)
gpio.output(ledVermelho, gpio.LOW)
gpio.output(ledVerde, gpio.LOW)

gpio.setup(pin_t, gpio.OUT)
gpio.setup(pin_e, gpio.IN)

# Estado da ocupação
ocupacao_atual = 0  # Inicialmente a lixeira está vazia
contador_aberturas = 0  # Contador de aberturas da lixeira

# Função para testar a conexão com a Internet
def testa_conexao():
    try:
        urlopen('https://www.google.com', timeout=1)
        return True
    except:
        return False

# Função para piscar o LED
def piscar_led(led, vezes, intervalo=0.5):
    for _ in range(vezes):
        gpio.output(led, gpio.HIGH)
        delay.sleep(intervalo)
        gpio.output(led, gpio.LOW)
        delay.sleep(intervalo)

# Função para controlar os LEDs conforme o estado
def controle_leds(ocupacao):
    if ocupacao >= 100:  # Lixeira cheia
        gpio.output(ledVerde, gpio.LOW)  # Apaga o LED verde
        gpio.output(ledVermelho, gpio.HIGH)  # Acende o LED vermelho
    else:  # Lixeira disponível
        gpio.output(ledVermelho, gpio.LOW)  # Apaga o LED vermelho
        gpio.output(ledVerde, gpio.HIGH)  # Acende o LED verde

# Função para medir a distância usando o sensor ultrassônico
def distancia():
    gpio.output(pin_t, True)
    delay.sleep(0.000001)
    gpio.output(pin_t, False)
    tempo_i = delay.time()
    while gpio.input(pin_e) == False:
        tempo_i = delay.time()
    while gpio.input(pin_e) == True:
        tempo_f = delay.time()
    temp_d = tempo_f - tempo_i
    distancia = (temp_d * 34300) / 2  # Calcula a distância em cm
    return distancia

# Função para enviar dados para o ThingSpeak
def enviar_para_thingspeak(distancia, contador):
    chave_api = 'S7TMLPDVTZ6YCET1'  # Substitua pela sua chave de API do ThingSpeak
    canal_id = '2757577'  # Substitua pelo ID do seu canal ThingSpeak
    
    # URL da API para escrever dados no ThingSpeak
    urlBase = 'https://api.thingspeak.com/update?api_key='
    keyWrite = 'S7TMLPDVTZ6YCET1'
    sensorDistancia = '&field1='
    sensorContador = '&field2='
    urlDados = (urlBase + keyWrite + sensorDistancia + str(distancia) + sensorContador + str(contador))
    
    # Envia a requisição POST
    try:
        requests.post(urlDados)  # Envia a requisição
        print(f"Dados enviados para o ThingSpeak: Distância {distancia} cm, Aberturas {contador}")
    except Exception as e:
        print(f"Erro ao enviar dados para o ThingSpeak: {e}")

# Rota principal
@app.route("/")
def index():
    if testa_conexao():
        dist = distancia()  # Medir a distância
        print(dist)

        # Se a distância for menor que 10 cm (indicando que a lixeira está cheia), pisca o LED vermelho 3 vezes
        if dist < 10:
            piscar_led(ledVermelho, 3)  # Pisca o LED vermelho 3 vezes
            controle_leds(100)  # Lixeira cheia, o LED vermelho acende

        # Envia a distância medida para o ThingSpeak
        enviar_para_thingspeak(dist, contador_aberturas)  # Enviar para o ThingSpeak

        # Atualiza o estado da ocupação e envia ao template
        templateData = {
            'ocupacao': f"{ocupacao_atual}%",
            'distancia': f"{dist} cm",  # Passa a distância medida para o template
            'aberturas': contador_aberturas  # Passa o número de aberturas para o template
        }
        return render_template('index.html', **templateData)
    else:
        return jsonify({'error': 'Sem conexão com a Internet.'}), 400

# Rota para abrir a tampa
@app.route("/abrir-tampa")
def abrir_tampa():
    global ocupacao_atual, contador_aberturas

    if not testa_conexao():
        return jsonify({'error': 'Sem conexão com a Internet.'}), 400

    if ocupacao_atual >= 100:  # Lixeira cheia
        # Pisca o LED vermelho 3 vezes quando tentar abrir com a lixeira cheia
        piscar_led(ledVermelho, 3)
        gpio.output(ledVermelho, gpio.HIGH)  # Deixa o LED vermelho aceso
        gpio.output(ledVerde, gpio.LOW)  # Apaga o LED verde
        return jsonify({'error': 'Lixeira cheia. Esvazie-a antes de abrir novamente.'}), 403

    # Incrementa a ocupação em 15% a cada abertura
    ocupacao_atual += 15
    ocupacao_atual = min(ocupacao_atual, 100)  # Garante que não ultrapasse 100%

    # Incrementa o contador de aberturas
    contador_aberturas += 1

    # Controle dos LEDs conforme o estado atual
    if ocupacao_atual >= 100:  # Se a lixeira estiver cheia
        piscar_led(ledVermelho, 3)  # Pisca o LED vermelho 3 vezes
        gpio.output(ledVermelho, gpio.HIGH)  # Acende o LED vermelho
        gpio.output(ledVerde, gpio.LOW)  # Apaga o LED verde
    else:  # Se a lixeira estiver disponível
        piscar_led(ledVerde, 3)  # Pisca o LED verde 3 vezes
        gpio.output(ledVerde, gpio.HIGH)  # Acende o LED verde
        gpio.output(ledVermelho, gpio.LOW)  # Apaga o LED vermelho

    return jsonify({'status': 'Tampa aberta', 'ocupacao': f"{ocupacao_atual}%", 'aberturas': contador_aberturas}), 200

@app.route("/fechar-tampa")
def fechar_tampa():
    global ocupacao_atual

    if not testa_conexao():
        return jsonify({'error': 'Sem conexão com a Internet.'}), 400

    # Se a lixeira não estiver cheia (ocupação menor que 100%), o LED verde será aceso
    if ocupacao_atual < 100:
        gpio.output(ledVerde, gpio.HIGH)  # Acende o LED verde
        gpio.output(ledVermelho, gpio.LOW)  # Apaga o LED vermelho
    else:
        gpio.output(ledVerde, gpio.LOW)  # Desliga o LED verde
        gpio.output(ledVermelho, gpio.HIGH)  # Acende o LED vermelho (quando a lixeira está cheia)

    return jsonify({'status': 'Tampa fechada', 'ocupacao': f"{ocupacao_atual}%", 'aberturas': contador_aberturas})


# Rota para esvaziar a lixeira
@app.route("/esvaziar-lixeira")
def esvaziar_lixeira():
    global ocupacao_atual

    ocupacao_atual = 0  # Reseta a ocupação para 0%
    controle_leds(ocupacao_atual)  # Ajusta os LEDs para o estado vazio

    return jsonify({'status': 'Lixeira esvaziada', 'ocupacao': '0%'}), 200