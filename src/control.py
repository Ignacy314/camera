from camera_control import PtzControl, PtzResponse


def control(cmd_q):
    cam = PtzControl("admin", "1plus2jest3")
    manual = False

    while True:
        cmd = cmd_q.get()
        print(f"control: cmd = '{cmd}'")

        if cmd == "stop":
            cmd_cont(cam, [0, 0, 0])
            break

        cmd = cmd.split(" ")
        sub_cmd = cmd[0]

        if sub_cmd == "m":
            sub_cmd = cmd[1]
            if sub_cmd == "on":
                manual = True
            elif sub_cmd == "off":
                manual = False
            elif sub_cmd == "c":
                cmd_cont(cam, cmd[2:])
            elif sub_cmd == "a":
                cmd_abs(cam, cmd[2:])
        elif sub_cmd == "a" and not manual:
            sub_cmd = cmd[1]
            if sub_cmd == "c":
                cmd_cont(cam, cmd[2:])
            elif sub_cmd == "a":
                cmd_abs(cam, cmd[2:])


def cmd_cont(cam, vals):
    try:
        resp = cam.continuous(float(vals[0]), float(vals[1]), float(vals[2]))
        if resp != PtzResponse.OK:
            print(resp)
    except Exception:
        pass


def cmd_abs(cam, vals):
    try:
        resp = cam.absolute(float(vals[0]), float(vals[1]), float(vals[2]))
        if resp != PtzResponse.OK:
            print(resp)
    except Exception:
        pass
