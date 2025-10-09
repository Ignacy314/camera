import asyncio
from websockets.asyncio.server import serve
import functools
import time
from timeit import default_timer as timer


async def _handler(
    websocket,
    stop_flag,
    coords_lon,
    coords_lat,
    coords_new,
    coords_timer,
    coords_lock,
):
    while True:
        if stop_flag.value == 1:
            break

        try:
            msg = await websocket.recv(decode=True)
            msg = msg.split(",")
            lon = float(msg[0])
            lat = float(msg[1])

            with coords_lock:
                coords_lon.value = lon
                coords_lat.value = lat
                coords_new.value = 1
                coords_timer.value = timer()

        except Exception:
            time.sleep(0.25)


async def _coords_recv(
    stop_flag,
    coords_lon,
    coords_lat,
    coords_new,
    coords_timer,
    coords_lock,
):
    handler = functools.partial(
        _handler,
        stop_flag=stop_flag,
        coords_lon=coords_lon,
        coords_lat=coords_lat,
        coords_new=coords_new,
        coords_timer=coords_timer,
        coords_lock=coords_lock,
    )

    while True:
        if stop_flag.value == 1:
            break
        start_server = serve(handler, "10.66.66.101", 3013)
        asyncio.get_event_loop().run_until_complete(start_server)
        time.sleep(0.25)


def coords_recv(
    stop_flag,
    coords_lon,
    coords_lat,
    coords_new,
    coords_timer,
    coords_lock,
):
    asyncio.run(
        _coords_recv(
            stop_flag,
            coords_lon,
            coords_lat,
            coords_new,
            coords_timer,
            coords_lock,
        )
    )
