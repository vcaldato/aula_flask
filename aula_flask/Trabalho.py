from flask import Flask, render_template, jsonify
import RPi.GPIO as gpio
import time as delay
import requests
from urllib.request import urlopen

# Configuração do GPIO
gpio.setmode(gpio.BOARD)
gpio.setwarnings(False)

# Pinos dos LEDs
ledVermelho, ledVerde = 11, 12

# Pinos do Sensor Ultrassônico
pin_t = 15  # Trigger
pin_e = 16  # Echo

# URL e chave para enviar os dados para o ThingSpeak
urlBase = 'https://api.thingspeak.com/update?api_key='
keyWrite = 'S7TMLPDVTZ6YCET1'
sensorDistancia = '&field1='

# Configuração dos pinos
gpio.setup(ledVermelho, gpio.OUT)
gpio.setup(ledVerde, gpio.OUT)
gpio.output(ledVermelho, gpio.LOW)
gpio.output(ledVerde, gpio.LOW)

gpio.setup(pin_t, gpio.OUT)
gpio.setup(pin_e, gpio.IN)

# Estado da ocupação
ocupacao_atual = 0  # Inicialmente a lixeira está vazia

# Função para testar a conexão com a Internet
def testa_conexao():
    try:
        urlopen('https://www.colegiomaterdei.com.br', timeout=1)
        return True
    except:
        return False

# Função para piscar o LED
def piscar_led(led, vezes, intervalo=0.2):
    for _ in range(vezes):
        gpio.output(led, gpio.HIGH)
        delay.sleep(intervalo)
        gpio.output(led, gpio.LOW)
        delay.sleep(intervalo)

# Função para enviar dados ao ThingSpeak usando POST
def enviar_ao_thingspeak(ocupacao):
    try:
        urlDados = f"{urlBase}{keyWrite}{sensorDistancia}{ocupacao}"
        retorno = requests.post(urlDados)

        if retorno.status_code == 200:
            print('Dados enviados com sucesso')
        else:
            print(f'Erro ao enviar dados: {retorno.status_code}')
    except Exception as e:
        print(f"Erro ao enviar dados ao ThingSpeak: {e}")

# Função para controlar os LEDs conforme o estado
def controle_leds(ocupacao):
    if ocupacao >= 100:  # Lixeira cheia
        gpio.output(ledVerde, gpio.LOW)  # Apaga o LED verde
        gpio.output(ledVermelho, gpio.HIGH)  # Acende o LED vermelho
    else:  # Lixeira disponível
        gpio.output(ledVermelho, gpio.LOW)  # Apaga o LED vermelho
        gpio.output(ledVerde, gpio.HIGH)  # Acende o LED verde

# Rota principal
@app.route("/")
def index():
    if testa_conexao():
        controle_leds(ocupacao_atual)  # Controle os LEDs com base na ocupação
        templateData = {
            'ocupacao': f"{ocupacao_atual}%",
        }
        return render_template('index.html', **templateData)
    else:
        return jsonify({'error': 'Sem conexão com a Internet.'}), 400

# Rota para abrir a tampa
@app.route("/abrir-tampa")
def abrir_tampa():
    global ocupacao_atual

    if not testa_conexao():
        return jsonify({'error': 'Sem conexão com a Internet.'}), 400

    if ocupacao_atual >= 100:  # Lixeira cheia
        piscar_led(ledVermelho, 3)  # Pisca o LED vermelho 3 vezes
        return jsonify({'error': 'Lixeira cheia. Esvazie-a antes de abrir novamente.'}), 403

    # Incrementa a ocupação em 15% a cada abertura
    ocupacao_atual += 15
    ocupacao_atual = min(ocupacao_atual, 100)  # Garante que não ultrapasse 100%

    controle_leds(ocupacao_atual)  # Ajusta os LEDs para o estado atual
    enviar_ao_thingspeak(ocupacao_atual)  # Envia os dados para o ThingSpeak

    return jsonify({'status': 'Tampa aberta', 'ocupacao': f"{ocupacao_atual}%"}), 200

# Rota para fechar a tampa
@app.route("/fechar-tampa")
def fechar_tampa():
    if not testa_conexao():
        return jsonify({'error': 'Sem conexão com a Internet.'}), 400

    # Aqui você pode definir ações específicas para fechar a tampa
    gpio.output(ledVerde, gpio.LOW)  # Desliga o LED verde
    gpio.output(ledVermelho, gpio.LOW)  # Desliga o LED vermelho

    return jsonify({'status': 'Tampa fechada'}), 200

# Rota para esvaziar a lixeira
@app.route("/esvaziar-lixeira")
def esvaziar_lixeira():
    global ocupacao_atual

    ocupacao_atual = 0  # Reseta a ocupação para 0%
    controle_leds(ocupacao_atual)  # Ajusta os LEDs para o estado vazio

    return jsonify({'status': 'Lixeira esvaziada', 'ocupacao': '0%'}), 200