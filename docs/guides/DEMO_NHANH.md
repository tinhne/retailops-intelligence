# Demo nhanh: một lệnh cho buổi gặp nhà tuyển dụng

Ghi chú ngắn để mở sản phẩm trên máy local và trình bày trong 5 phút. Kịch bản đầy đủ 15 phút và
giải thích từng màn hình nằm ở [`HUONG_DAN_DEMO_VA_TRIEN_KHAI.md`](HUONG_DAN_DEMO_VA_TRIEN_KHAI.md).

## 1. Chuẩn bị một lần

- Cài **Docker Desktop** và bật lên. Nên để Docker được dùng ít nhất 4 GB RAM (Settings → Resources).
- Có lệnh `make`. Trên macOS, nếu chưa có thì cài bằng `xcode-select --install`.
- Clone repo:

```bash
git clone https://github.com/tinhne/retailops-intelligence.git
```

Lần chạy đầu cần Internet để tải image và thư viện.

## 2. Trước buổi demo khoảng 10 phút

Trong thư mục `retailops-intelligence`:

```bash
make demo
```

Lệnh này làm 4 việc:

1. Kiểm tra Docker đã chạy chưa.
2. Build và khởi động database, API, worker và web. Lần đầu mất vài phút; các lần sau khoảng 1 phút
   vì Docker dùng lại phần đã build.
3. **Tạo lại dữ liệu demo theo giờ hiện tại**, nên đơn hàng, ngoại lệ và biểu đồ luôn "mới", dù
   lần demo trước đã cách vài tuần.
4. Bật đăng nhập cho các tài khoản nhân viên giả lập, rồi in ra địa chỉ, tài khoản và mật khẩu.

Kết thúc, màn hình in ra như sau (mật khẩu của bạn sẽ khác):

```text
RetailOps Intelligence is running, with demo data generated just now (all of it fictional).

  Open       http://127.0.0.1:3000
  Viewer     "Explore the demo" on the sign-in page: read-only, no password
  Staff      manager@kestrel.example (also owner@, staff@, sofia@, analyst@kestrel.example)
  Password   demo-…   (kept in .env, the same next time)
  API docs   http://127.0.0.1:8000/api/docs
```

Mở <http://127.0.0.1:3000>, bấm thử **Explore the demo** và đăng nhập thử `manager@kestrel.example`
để chắc mọi thứ chạy.

> Dùng `127.0.0.1` thay cho `localhost`. Nếu máy đang chạy một ứng dụng khác ở cổng 3000,
> `localhost` có thể mở nhầm sang ứng dụng đó.

## 3. Tài khoản

| Đăng nhập | Vai trò | Dùng khi |
|---|---|---|
| Nút **Explore the demo** | Viewer, chỉ đọc | Phần xem: Overview, ngoại lệ, AI, copilot |
| `manager@kestrel.example` | Manager | Phần thao tác: nhận việc, ghi chú, xử lý, nhập CSV |
| `owner@kestrel.example` | Owner | Users & roles, Settings, Audit log |

Mật khẩu nhân viên được tạo ở lần chạy đầu và lưu trong file `.env` (không đưa lên Git). Quên thì
chạy lại `make demo` để xem, hoặc `grep DEMO_STAFF_PASSWORD .env`.

## 4. Kịch bản 5 phút

| Phút | Làm gì | Ý chính muốn nói |
|---|---|---|
| 0:00 | **Explore the demo** → **Overview** | Mỗi sáng quản lý mở màn hình này: ngoại lệ đang mở, xếp theo điểm ưu tiên chứ không theo thời gian |
| 1:00 | Mở ngoại lệ đầu tiên: *Why this priority*, *Evidence* | Điểm 0–100 có 5 thành phần nhìn thấy được; mỗi con số liên kết tới bản ghi gốc. Phát hiện bằng 9 quy tắc cố định, không phải AI |
| 2:00 | **Generate investigation**, rồi **Copilot** với câu hỏi gợi ý | AI chỉ đọc qua 11 công cụ chỉ-đọc, mỗi dữ kiện có tham chiếu; không có API key thì engine quy tắc vẫn trả lời |
| 3:00 | Đăng xuất → `manager@kestrel.example` → một ngoại lệ **Open**: **Acknowledge**, **Start work**, **Resolve…** | Vòng đời có kiểm soát; xử lý xong vẫn chờ lần nhập dữ liệu sau xác minh, sai thì tự mở lại |
| 4:00 | **Imports → New import** hoặc **Audit log** | Nhập CSV có kiểm tra và xem trước; mọi thay đổi đều ghi người làm và thời gian |
| 4:30 | Kết | Backend gần 900 test với PostgreSQL thật, Playwright end-to-end, quét trợ năng WCAG, CI 5 job trên GitHub Actions |

Câu hỏi hay gặp và câu trả lời ngắn: mục 3 của
[`HUONG_DAN_DEMO_VA_TRIEN_KHAI.md`](HUONG_DAN_DEMO_VA_TRIEN_KHAI.md#câu-hỏi-hay-gặp-khi-demo).

## 5. Sau buổi demo

```bash
make down    # tắt, giữ dữ liệu
make demo    # lần sau: bật lại với dữ liệu demo mới
make reset   # tắt và XOÁ toàn bộ dữ liệu local (database Docker)
```

## 6. Sự cố thường gặp

| Hiện tượng | Cách xử lý |
|---|---|
| `Docker is not running` | Mở Docker Desktop, đợi tới khi báo *Engine running*, chạy lại `make demo` |
| `localhost:3000` mở ra ứng dụng khác | Dùng <http://127.0.0.1:3000> |
| `port is already allocated` | Cổng đang bị chiếm. Đổi cổng: `WEB_HOST_PORT=3100 make demo`, rồi mở <http://127.0.0.1:3100>. Tương tự `API_HOST_PORT`, `POSTGRES_HOST_PORT` |
| Đăng nhập nhân viên báo sai mật khẩu | Chạy lại `make demo`: dữ liệu demo được tạo lại với đúng mật khẩu trong `.env` |
| Copilot ghi *deterministic* ở cuối câu trả lời | Bình thường: chưa cấu hình key AI nên engine quy tắc trả lời. Muốn dùng Gemini miễn phí, đặt `LLM_PROVIDER=gemini` và `GEMINI_API_KEY` trong `.env` |
| Build lần đầu rất chậm hoặc báo hết bộ nhớ | Tăng RAM cho Docker Desktop, tắt bớt container khác (`docker compose ls` để xem) |

Nhà tuyển dụng muốn tự chạy trên máy họ: chỉ cần Docker và hai lệnh ở mục 1 và 2. Trên Windows chưa
có `make`, dùng `docker compose up --build` rồi bấm **Explore the demo** (chỉ có chế độ xem).
