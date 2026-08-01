# capture.py
#  takes in serial data from ESP32 in the format of
#  ms ch0 ch1 ch2 ch3 ch4 ch5 ch6 ch7


from collections import deque

import matplotlib.pyplot as plt
import serial
from matplotlib.animation import FuncAnimation


PORT = "COM4"
BAUD = 115200
WINDOW_SECONDS = 30
CHANNELS = 8

ser = None
fig = None
ax = None
lines = []

times = deque()
pressures = [deque() for _ in range(CHANNELS)]
first_timestamp = None

# update
#  automatically updates the plot based on variables WINDOW_SECONDS and CHANNELS (# of sensors)

def update(_):
    global first_timestamp

    while ser.in_waiting:
        text = ser.readline().decode("ascii", errors="ignore").strip()
        parts = text.split(",")

        # timestamp + eight pressures
        if len(parts) != CHANNELS + 1:
            continue

        try:
            timestamp = int(parts[0])
            values = [float(value) for value in parts[1:]]
        except ValueError:
            continue

        if first_timestamp is None:
            first_timestamp = timestamp

        time_s = (timestamp - first_timestamp) / 1000.0

        times.append(time_s)

        for channel, value in zip(pressures, values):
            channel.append(value)

        print(timestamp, *values)

        # Remove data older than the plotting window.
        while times and time_s - times[0] > WINDOW_SECONDS:
            times.popleft()

            for channel in pressures:
                channel.popleft()

    if times:
        for line, channel in zip(lines, pressures):
            line.set_data(times, channel)

        ax.set_xlim(
            max(0, times[-1] - WINDOW_SECONDS),
            max(WINDOW_SECONDS, times[-1]),
        )

        ax.relim()
        ax.autoscale_view(scalex=False)

    return lines


def main():
    global ser, fig, ax, lines

    ser = serial.Serial(PORT, BAUD, timeout=0)

    fig, ax = plt.subplots(figsize=(11, 5))

    lines = [
        ax.plot([], [], label=f"Sensor {i + 1}")[0]
        for i in range(CHANNELS)
    ]

    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Pressure (kPa)")
    ax.set_title("Live Pressure Sensor Data")
    ax.grid(alpha=0.3)
    ax.legend(ncol=4)

    animation = FuncAnimation(
        fig,
        update,
        interval=50,
        cache_frame_data=False,
    )

    print(f"Reading eight sensors from {PORT}")

    try:
        plt.show()
    finally:
        ser.close()


if __name__ == "__main__":
    main()