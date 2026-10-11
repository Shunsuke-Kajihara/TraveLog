import json
import os
from flask import Flask, redirect, render_template, request
from werkzeug.utils import secure_filename
from datetime import date
import base64

app = Flask(__name__)

UPLOAD_FOLDER = "static/uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# デフォルトの固定為替レート（対 JPY）
DEFAULT_RATES = {
    "JPY": 1.0,
    "USD": 157.8,
    "EUR": 165.0,
    "KRW": 0.11,
    "GBP": 195.0,
    "CNY": 23.5,
    "GEL": 60.5,
    "UZS": 0.013,
}

SUPPORTED_CURRENCIES = ["JPY", "USD", "EUR", "KRW", "GBP", "CNY", "GEL", "UZS"]


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def load_trip_data(trip_id):
    file_path = f"data/{trip_id}/data.json"
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def save_trip_data(trip_id, data):
    folder_path = f"data/{trip_id}"
    os.makedirs(folder_path, exist_ok=True)
    file_path = f"{folder_path}/data.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


@app.route("/")
@app.route("/")
def index():
    trips = []
    if os.path.exists("data"):
        for trip_id in os.listdir("data"):
            data = load_trip_data(trip_id)
            if data:
                trips.append(data)
                
    today_str = date.today().strftime("%Y-%m-%d") # 今日を "YYYY-MM-DD" で取得
    
    return render_template(
        "index.html", 
        trips=trips, 
        supported_currencies=SUPPORTED_CURRENCIES,
        today=today_str # テンプレートに渡す
    )


@app.route("/add_trip", methods=["POST"])
def add_trip():
    title = request.form.get("title")
    start_date = request.form.get("start_date")
    end_date = request.form.get("end_date")
    currencies = request.form.getlist("currencies")

    if not currencies:
        currencies = ["JPY"]

    trip_id = title.lower().replace(" ", "_")

    data = {
        "id": trip_id,
        "title": title,
        "start_date": start_date,
        "end_date": end_date,
        "currencies": currencies,
        "exchange_rates": DEFAULT_RATES,
        "expenses": [],
        "photos": [],
        "itinerary": [],
    }

    save_trip_data(trip_id, data)
    return redirect("/")


@app.route("/trip/<trip_id>")
def trip_detail(trip_id):
    data = load_trip_data(trip_id)
    if not data:
        return "旅行データが見つかりません", 404

    tab = request.args.get("tab", "itinerary")

    expenses = data.get("expenses", [])
    photos = data.get("photos", [])
    itinerary = data.get("itinerary", [])

    total_expense = sum(e.get("converted_amount", 0) for e in expenses)

    # 支出データをインデックス（idx）付きでグループ化
    grouped_expenses = {}
    for idx, e in enumerate(expenses):
        cat = e.get("category", "その他")
        converted = e.get("converted_amount", 0)

        if cat not in grouped_expenses:
            grouped_expenses[cat] = {"list": [], "subtotal": 0}

        # 削除時にインデックスを使うため保持
        e_with_idx = dict(e)
        e_with_idx["idx"] = idx
        grouped_expenses[cat]["list"].append(e_with_idx)
        grouped_expenses[cat]["subtotal"] += converted

    # 旅程データにも元のインデックスを紐付け
    itinerary_with_idx = []
    for idx, item in enumerate(itinerary):
        item_copy = dict(item)
        item_copy["idx"] = idx
        itinerary_with_idx.append(item_copy)

    sorted_itinerary = sorted(
        itinerary_with_idx, key=lambda x: (x.get("date", ""), x.get("time", ""))
    )

    grouped_photos = {}
    album_covers = {}

    # 写真データにもインデックスを紐付け
    for idx, p in enumerate(photos):
        album = p.get("album", "未分類")
        if album not in grouped_photos:
            grouped_photos[album] = []
        p_copy = dict(p)
        p_copy["idx"] = idx
        grouped_photos[album].append(p_copy)
        album_covers[album] = p.get("path")

    if "未分類" not in grouped_photos:
        grouped_photos["未分類"] = []

    return render_template(
        "detail.html",
        trip=data,
        active_tab=tab,
        total_expense=total_expense,
        grouped_expenses=grouped_expenses,
        photos=photos,
        grouped_photos=grouped_photos,
        album_covers=album_covers,
        itinerary=sorted_itinerary,
        supported_currencies=SUPPORTED_CURRENCIES,
    )


@app.route("/trip/<trip_id>/add_expense", methods=["POST"])
def add_expense(trip_id):
    data = load_trip_data(trip_id)
    if not data:
        return "旅行データが見つかりません", 404

    item = request.form.get("item")
    amount = float(request.form.get("amount", 0))
    currency = request.form.get("currency", "JPY")
    category = request.form.get("category", "その他")

    rates = data.get("exchange_rates", DEFAULT_RATES)
    rate = rates.get(currency, 1.0)
    converted_amount = int(round(amount * rate))

    if "expenses" not in data:
        data["expenses"] = []

    data["expenses"].append(
        {
            "item": item,
            "amount": amount,
            "currency": currency,
            "converted_amount": converted_amount,
            "category": category,
        }
    )
    save_trip_data(trip_id, data)

    return redirect(f"/trip/{trip_id}?tab=expenses")


# 【追加】支出の削除処理
@app.route("/trip/<trip_id>/delete_expense/<int:idx>", methods=["POST"])
def delete_expense(trip_id, idx):
    data = load_trip_data(trip_id)
    if data and "expenses" in data:
        if 0 <= idx < len(data["expenses"]):
            data["expenses"].pop(idx)
            save_trip_data(trip_id, data)
    return redirect(f"/trip/{trip_id}?tab=expenses")


@app.route("/trip/<trip_id>/update_currencies", methods=["POST"])
def update_currencies(trip_id):
    data = load_trip_data(trip_id)
    if not data:
        return "旅行データが見つかりません", 404

    selected_currencies = request.form.getlist("currencies")
    if not selected_currencies:
        selected_currencies = ["JPY"]

    data["currencies"] = selected_currencies
    save_trip_data(trip_id, data)

    return redirect(f"/trip/{trip_id}?tab=expenses")


@app.route("/trip/<trip_id>/add_photo", methods=["POST"])
def add_photo(trip_id):
    data = load_trip_data(trip_id)
    if not data:
        return "旅行データが見つかりません", 404

    # JSONリクエストとして受け取る
    req_data = request.get_json()
    if not req_data or "photos" not in req_data:
        return {"error": "No photos provided"}, 400

    photos_payload = req_data["photos"]  # [{name, data (base64)}, ...]
    caption = req_data.get("caption", "")
    album = req_data.get("album", "未分類").strip()
    if not album:
        album = "未分類"

    if "photos" not in data:
        data["photos"] = []

    trip_upload_folder = os.path.join(app.config["UPLOAD_FOLDER"], trip_id)
    os.makedirs(trip_upload_folder, exist_ok=True)

    for item in photos_payload:
        filename = secure_filename(item["name"])
        base64_str = item["data"]

        try:
            # "data:image/jpeg;base64,xxxx..." のようなプレフィックスがあれば剥がす
            if "," in base64_str:
                base64_str = base64_str.split(",")[1]

            file_bytes = base64.b64decode(base64_str)

            save_path = os.path.join(trip_upload_folder, filename)
            with open(save_path, "wb") as f:
                f.write(file_bytes)

            web_path = f"/static/uploads/{trip_id}/{filename}"
            data["photos"].append(
                {"path": web_path, "caption": caption, "album": album}
            )
        except Exception as e:
            print(f"Error saving photo {filename}: {e}")

    save_trip_data(trip_id, data)
    return {"status": "success"}, 200


# 【追加】写真の削除処理（実ファイルも削除）
@app.route("/trip/<trip_id>/delete_photo/<int:idx>", methods=["POST"])
def delete_photo(trip_id, idx):
    data = load_trip_data(trip_id)
    if data and "photos" in data:
        if 0 <= idx < len(data["photos"]):
            target_photo = data["photos"].pop(idx)
            # 画像ファイルの削除処理
            file_path = target_photo.get("path", "").lstrip("/")
            if os.path.exists(file_path):
                os.remove(file_path)
            save_trip_data(trip_id, data)
    return redirect(f"/trip/{trip_id}?tab=photos")


@app.route("/trip/<trip_id>/add_itinerary", methods=["POST"])
def add_itinerary(trip_id):
    data = load_trip_data(trip_id)
    if not data:
        return "旅行データが見つかりません", 404

    date = request.form.get("date")
    time = request.form.get("time")
    title = request.form.get("title")
    memo = request.form.get("memo", "")

    if "itinerary" not in data:
        data["itinerary"] = []

    data["itinerary"].append(
        {"date": date, "time": time, "title": title, "memo": memo}
    )
    save_trip_data(trip_id, data)

    return redirect(f"/trip/{trip_id}?tab=itinerary")


# 【追加】旅程の削除処理
@app.route("/trip/<trip_id>/delete_itinerary/<int:idx>", methods=["POST"])
def delete_itinerary(trip_id, idx):
    data = load_trip_data(trip_id)
    if data and "itinerary" in data:
        if 0 <= idx < len(data["itinerary"]):
            data["itinerary"].pop(idx)
            save_trip_data(trip_id, data)
    return redirect(f"/trip/{trip_id}?tab=itinerary")
    
@app.route('/service-worker.js')
def service_worker():
    return app.send_static_file('service-worker.js')

@app.route('/manifest.json')
def manifest():
    return app.send_static_file('manifest.json')

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)