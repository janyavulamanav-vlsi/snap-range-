import os, tempfile, shutil, glob
from flask import Flask, request, jsonify, send_file, send_from_directory, after_this_request
import yt_dlp
from yt_dlp.utils import download_range_func

app = Flask(__name__)
HERE = os.path.dirname(os.path.abspath(__file__))

@app.after_request
def cors(r):
    r.headers["Access-Control-Allow-Origin"] = os.environ.get("ALLOW_ORIGIN", "*")
    r.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return r

@app.route("/api/info", methods=["OPTIONS"])
def opts():
    return "", 204

@app.get("/")
def index():
    return send_from_directory(HERE, "index.html")

@app.post("/api/info")
def info():
    url = (request.json or {}).get("url", "").strip()
    if not url.startswith(("http://", "https://")):
        return jsonify(error="Paste a full link starting with https://"), 400
    try:
        with yt_dlp.YoutubeDL({"quiet": True, "noplaylist": True}) as ydl:
            d = ydl.extract_info(url, download=False)
        return jsonify(title=d.get("title"), duration=d.get("duration") or 0,
                       thumbnail=d.get("thumbnail"), site=d.get("extractor_key"))
    except Exception as e:
        return jsonify(error="Couldn't read that link. It may be private or unsupported."), 400

@app.get("/api/download")
def download():
    url = request.args.get("url", "")
    start = float(request.args.get("start") or 0)
    end = float(request.args.get("end") or 0)
    kind = request.args.get("kind", "video")   # video | audio
    height = request.args.get("height", "720")
    tmp = tempfile.mkdtemp()
    opts = {"quiet": True, "noplaylist": True, "outtmpl": os.path.join(tmp, "%(title).80s.%(ext)s")}
    if kind == "audio":
        opts.update(format="bestaudio/best", postprocessors=[{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}])
    else:
        opts.update(format=f"bv*[height<={height}]+ba/b[height<={height}]/b", merge_output_format="mp4")
    if end > start:
        opts["download_ranges"] = download_range_func(None, [(start, end)])
        opts["force_keyframes_at_cuts"] = True
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
        path = glob.glob(os.path.join(tmp, "*"))[0]
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        return jsonify(error="Download failed."), 500

    @after_this_request
    def cleanup(resp):
        shutil.rmtree(tmp, ignore_errors=True)
        return resp
    return send_file(path, as_attachment=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
