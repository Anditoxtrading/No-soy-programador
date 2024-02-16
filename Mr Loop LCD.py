import time
import sys
import threading
from pybit.unified_trading import HTTP
import config



session = HTTP(
    testnet=False,
    api_key=config.api_key,
    api_secret=config.api_secret,
)

# Parámetros para LCD
simbolo = input('INGRESE EL TICK A OPERAR: ') + "USDT"
qty = float(input('INGRESE LA CANTIDAD DE MONEDAS QUE VA A COMPRAR: '))
LCD_threshold = float(input('INGRESE LA CANTIDAD DE MONEDAS QUE NO VA A DESCARGAR: '))
factor_multiplicador_distancia = float(input('INGRESE EL %PORCENTAJE DE DISTANCIA PARA LAS RECOMPRAS: '))
cant_recompras = int(input('INGRESE LA CANTIDAD DE RECOMPRAS: '))




# Factor multiplicador para las recompras
factor_multiplicador_cantidad = 0.40 
qty_str = -LCD_threshold


try:
    # Obtener la lista actualizada de posiciones
    response_positions = session.get_positions(
        category="linear",
        symbol=simbolo,
    )

    # Verificar si la solicitud fue exitosa (retCode 0 significa éxito)
    if response_positions['retCode'] == 0:
        # Acceder a la información de la posición
        positions_list = response_positions['result']['list']

        # Verificar si hay posiciones en la lista y si alguna está abierta
        if positions_list and any(position['size'] != '0' for position in positions_list):
            print(f"Ya hay una posición abierta en: {simbolo}. No se abrirá otra posición.")
        else:
            # Coloca la orden de mercado si no hay posiciones abiertas
            response_market_order = session.place_order(
                category="linear",
                symbol=simbolo,
                side="Buy",
                orderType="Market",
                qty=qty,
            )
            print(f"Abriendo posición para {simbolo} : {response_market_order}")
    else:
        print("Error al obtener las posiciones.")
except Exception as e:
    print(f"Error: {e}")

# Espera 5 segundos (o el tiempo necesario para que la orden de mercado se complete)
time.sleep(5)

def main():
                  
    def primer_bucle():
        while True:
            try:

                # Obtener la lista actualizada de posiciones
                response_positions = session.get_positions(
                    category="linear",
                    symbol=simbolo,
                )

                # Verificar si la solicitud fue exitosa (retCode 0 significa éxito)
                if response_positions['retCode'] == 0:
                    # Acceder a la información de la posición
                    positions_list = response_positions['result']['list']

                    # Verificar si hay posiciones en la lista
                    if positions_list:
                        # Obtener el precio actual de la posición
                        current_price = float(positions_list[0]['avgPrice'])

                        
                        # Tamaño para las órdenes límite
                        size = float(positions_list[0]['size'])

                        # Redondear hacia abajo si es necesario
                        size = int(size) if size.is_integer() else size

                        size_nuevo=size
                        
                        # calcular el precio del SL
                        distancia_sl = (cant_recompras * factor_multiplicador_distancia / 100) + 0.006
                        price_sl = current_price - (current_price * distancia_sl)
                    
                        # Verificar si no hay órdenes limit abiertas
                        limit_orders = (session.get_open_orders(category="linear", symbol=simbolo, openOnly=0, limit=10,)) 

                        # Filtrar solo las órdenes límite de compra (Buy)
                        ordenes_abiertas = [
                            order for order in limit_orders.get('result', {}).get('list', [])
                            if order.get('side') == 'Buy'
                        ]

                        # Verificar si la cantidad de monedas es igual o menor que el umbral LCD_threshold y no hay órdenes limit abiertas
                        if float(positions_list[0]['size']) <= LCD_threshold and len(ordenes_abiertas) == 0:                     
                            print("PREPARANDOSE PARA COLOCAR LAS RECOMPRAS Y EL STOP LOSS")
                            
                            # PONER ORDEN STOP LOSS
                            orden_SL=session.set_trading_stop(category="linear", symbol=simbolo, stopLoss=price_sl, slTriggerB="IndexPrice",tpslMode="Full", slOrderType="Market",)
                            print(f"Colocando Stop Loss en {simbolo} : {orden_SL}")
                            
                            # Abre órdenes límite con porcentajes de distancia y cantidad progresivos
                            for i in range(1, cant_recompras + 1):
                                porcentaje_distancia = 0.01 * i * factor_multiplicador_distancia  # Aumenta progresivamente
                                cantidad_orden = size_nuevo * (1 + factor_multiplicador_cantidad)

                                # Verifica si el tamaño nuevo tiene decimales
                                if isinstance(size_nuevo, int):
                                    cantidad_orden = int(cantidad_orden)  # Redondea hacia abajo si es un número entero
                                else:
                                    cantidad_orden = round(cantidad_orden, len(str(size_nuevo).split('.')[1]))
                                

                                size_nuevo = cantidad_orden # Actualiza size para la siguiente iteración

                                # Calcula el precio para la orden límite
                                precio_orden_limite = current_price - (current_price * porcentaje_distancia)

                                # Coloca la orden límite
                                response_limit_order = session.place_order(
                                    category="linear",
                                    symbol=simbolo,
                                    side="Buy",
                                    orderType="Limit",
                                    qty=str(cantidad_orden),
                                    price=str(precio_orden_limite),
                                )
                       
                                # Imprime la respuesta de la orden límite
                                print(f"Colocando orden Límite {i} en {simbolo}: {response_limit_order}")

                        else:
                            print(f"Verificando recompras en {simbolo}")
                            time.sleep(300)
                    else:
                        print(f"No hay posiciones en la lista en {simbolo} Esperando...")
                        time.sleep(5)

            except Exception as e:
                print(f"Error en el primer bucle en {simbolo}: {e}")
                time.sleep(5)
 
    def segundo_bucle():
        while True:
            try: 
                # Configuración del Take Profit (Segundo bucle)
                distancia_LCD = 0.01
                

                # Obtener información sobre las posiciones abiertas
                positions_response = session.get_positions(category="linear", symbol=simbolo)
                precio_entrada_original = float(positions_response['result']['list'][0]['avgPrice'])

                while True:
                    try:
                        # Obtener información sobre las posiciones abiertas
                        positions_response = session.get_positions(category="linear", symbol=simbolo)
                        precio_entrada_actual = float(positions_response['result']['list'][0]['avgPrice'])
                        tamaño_for_takeprofit = float(positions_response['result']['list'][0]['size'])
                        take_profit_qty = tamaño_for_takeprofit - LCD_threshold
                        take_profit_qty=round(take_profit_qty, len(str(tamaño_for_takeprofit).split('.')[1]))
                                

                        if precio_entrada_actual != precio_entrada_original:
                            
                            # Obtener órdenes límite abiertas
                            open_orders_responsetp = session.get_open_orders(category="linear", symbol=simbolo, openOnly=0, limit=1,)                  

                            # Filtrar solo las órdenes límite de venta (Sell)
                            sell_limit_orders = [order for order in open_orders_responsetp.get('result', {}).get('list', [])
                                                if order.get('orderType') == "Limit" and order.get('side') == 'Sell']


                            # Iterar sobre las órdenes límite de venta para obtener y cancelar cada una
                            for order in sell_limit_orders:
                                take_profit_order_id = order['orderId']
                                cancel_response = session.cancel_order(category="linear", symbol=simbolo, orderId=take_profit_order_id)
                                if 'result' in cancel_response and cancel_response['result']:   
                                    mensaje_canceltp=(f"Orden de take profit existente cancelada con éxito en {simbolo}: {cancel_response}")
                                    print(mensaje_canceltp)
                                else:
                                    error_canceltp=(f"Error al cancelar la orden de take profit existente en {simbolo}: {cancel_response}")
                                    print(error_canceltp)


                            # Actualizar el precio de entrada original con el precio de entrada actual
                            precio_entrada_original = precio_entrada_actual

                            # Calcular el nuevo precio para la orden de take profit
                            precio_orden_takeprofit = precio_entrada_actual + (precio_entrada_actual * distancia_LCD)

                            # Abrir la nueva orden de take profit
                            take_profit_order_response = session.place_order(
                                category="linear",
                                symbol=simbolo,
                                side="Sell",
                                orderType="Limit",
                                qty=str(take_profit_qty),
                                price=str(precio_orden_takeprofit),
                            )

                            # Extraer información relevante de la respuesta de la API
                            if 'result' in take_profit_order_response:
                                order_id = take_profit_order_response['result'].get('orderId', 'No ID')
                                mensaje_tp = f"Orden de take profit abierta en {simbolo}. ID de la orden: {order_id}"
                            else:
                                mensaje_tp = f"Error al abrir la orden de take profit en {simbolo}. Detalles: {take_profit_order_response}"

                            # Enviar el mensaje a través de Telegram
                            print(mensaje_tp)


                        else:
                            print("La posicion aun no se ha cargado para poner take profit")

                        # Esperar antes de la próxima iteración (ajusta según tus necesidades)
                        time.sleep(300)

                    except Exception as e:
                        error_tp1=(f"Se produjo un error durante la verificación: {e}")
                        print(error_tp1)
                        
                        # Manejar el error según sea necesario

                    # Esperar antes de la próxima iteración del bucle interno
                    time.sleep(120)

            except Exception as e:
                error_tp2=(f"Se produjo un error en el segundo bucle: {e}")
                print(error_tp2)
            # Esperar antes de la próxima iteración del bucle externo
            time.sleep(10)

    def tercer_bucle():
        while True:
            try:
                # Obtener información sobre las posiciones abiertas
                response_for_cancel = session.get_positions(category="linear", symbol=simbolo)
                tamaño_for_cancel = float(response_for_cancel['result']['list'][0]['size'])
                

                # Obtener órdenes límite abiertas
                open_orders_response = session.get_open_orders(
                    category="linear",
                    symbol=simbolo,
                    openOnly=0,
                    limit=10,
                )                  

                # Filtrar solo las órdenes límite de compra (Buy)
                buy_limit_orders = [
                    order for order in open_orders_response.get('result', {}).get('list', [])
                    if order.get('side') == 'Buy'
                ]

                # Verificar si hay menos de 6 órdenes límite de compra y el tamaño de la posición es igual o menor que el umbral
                if tamaño_for_cancel <= LCD_threshold and len(buy_limit_orders) < cant_recompras:
                    # Cancelar SL
                    cancel_sl =session.cancel_all_orders(category="linear", symbol=simbolo, orderFilter="StopOrder" ) 
                    print(f"Orden Stop Loss cancelada con exito en {simbolo}: {cancel_sl}")
                    
                    # Cancelar todas las órdenes abiertas
                    for order in buy_limit_orders:                                    
                        order_id = order['orderId']
                        cancel_response = session.cancel_order(category="linear", symbol=simbolo, orderId=order_id)

                        if 'result' in cancel_response and cancel_response['result']:
                            print(f"Orden de compra cancelada con éxito en {simbolo}. Order ID: {order_id}")
                        else:
                            print(f"Error al cancelar la orden de compra en {simbolo}. Order ID: {order_id}")
                else:
                    print(f"{simbolo}:No es necesario cancelar las recompras aún, esperando...")

                time.sleep(300)

            except Exception as e:
                print(f"Error en el tercer bucle {simbolo}: {e}")
                time.sleep(5)

    # Crear hilos para cada bucle
    hilo_primer_bucle = threading.Thread(target=primer_bucle)
    hilo_segundo_bucle = threading.Thread(target=segundo_bucle)
    hilo_tercer_bucle = threading.Thread(target=tercer_bucle)

    # Iniciar los hilos
    hilo_primer_bucle.start()
    time.sleep(10)  # Esperar 10 segundos antes de iniciar los próximos bucles
    hilo_segundo_bucle.start()
    hilo_tercer_bucle.start()

    # Esperar a que los hilos terminen 
    hilo_primer_bucle.join()
    time.sleep(10)
    hilo_segundo_bucle.join()
    hilo_tercer_bucle.join()

if __name__ == "__main__":
    while True:
        try:
            main()
        except Exception as e:
            print(f"Se produjo un error: {e}")
            print("Reiniciando los bucles en 30 segundos...")
            time.sleep(30)  # Esperar 30 segundos antes de reiniciar los bucles
            continue

