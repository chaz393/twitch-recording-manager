import threading
import subprocess


class RecordingThread(threading.Thread):
    def __init__(self, full_path, streamer_name, thread_finished_callback):
        threading.Thread.__init__(self)
        self.stop_event = threading.Event()
        self.full_path = full_path
        self.streamer_name = streamer_name
        self.thread_finished_callback = thread_finished_callback

    def run(self):
        print(f"starting {self.streamer_name}")
        process = self.start_recording(self.full_path, self.streamer_name)
        # wait while stop is not set AND the process is running
        while not self.stop_event.is_set() and process.poll() is None:
            self.stop_event.wait(1)
        if self.stop_event.is_set():  # if we need to stop, terminate the process
            process.terminate()
        while process.poll is None:  # wait for process to end
            self.stop_event.wait(1)
        print(f"{self.streamer_name} stopping")
        self.thread_finished_callback(self.ident, self.full_path, self.streamer_name)

    @staticmethod
    def start_recording(full_path: str, streamer_name: str):
        params = ["streamlink", "-o", full_path, f"https://www.twitch.tv/{streamer_name}", "best",
                  "--twitch-disable-hosting"]
        return subprocess.Popen(params)
