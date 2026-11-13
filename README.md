# Hệ Thống AI Agent Xử Lý Cơ Hội Bán Hàng B2B - Công Ty Minh An

Hệ thống AI Agent tự động hóa chu trình tiếp nhận, thẩm định và phản hồi yêu cầu mua thiết bị, dịch vụ công nghệ cho khách hàng doanh nghiệp của **Công ty Minh An**, bám sát 100% sơ đồ quy trình nghiệp vụ:

```
[Bắt đầu: Tiếp nhận yêu cầu] 
        ↓
[Phân loại & Kiểm tra thông tin]
        ↓
    <Có đủ thông tin?>
       ├── (Không) ──> [Yêu cầu KH làm rõ / bổ sung] ──> (Quay lại Tiếp nhận)
       └── (Có)
             ↓
[Tạo Hồ sơ Cơ hội & Gắn người phụ trách (6 NVKD)]
             ↓
[Thẩm định tồn kho & giá hiện hành (Vận hành & Kho)]
             ↓
[Lập Báo giá & Dự thảo đề xuất]
             ↓
    <Có vượt thẩm quyền / Cần chiết khấu đặc biệt?>
       ├── (Có) ───> [Trưởng phòng duyệt] ──┐
       └── (Không) ──────────────────────────┴──> [Kết thúc: Cập nhật & Theo dõi CRM]
```

---

## 1. Các Vấn Đề Được Giải Quyết Triệt Để

| Vấn đề trước đây của Minh An | Cơ chế AI Agent xử lý |
| :--- | :--- |
| **Bỏ sót hạng mục** | Phân tích thực thể (Named Entity Recognition), tách danh sách sản phẩm/dịch vụ theo từng dòng và map chính xác mã SKU. |
| **Dùng giá cũ** | Tra cứu trực tiếp bảng giá hiện hành tại `data/products.json` theo thời gian thực tại thời điểm tiếp nhận. |
| **Hứa sai thời hạn giao hàng** | Đối soát số lượng yêu cầu với `available_stock`. Nếu thiếu tồn kho, tự động cộng `restock_lead_days` và cảnh báo xung đột thời hạn nếu KH yêu cầu gấp. Đề xuất phương án giao 2 đợt. |
| **Yêu cầu bị trôi nổi** | Thuật toán cân bằng tải tự động gán cơ hội cho 1 trong 6 NVKD và lưu vào CRM Pipeline kèm theo dõi SLA. |
| **Vượt quyền duyệt** | Đánh giá mức chiết khấu đề xuất: NVKD tự quyết $\le 5\%$; từ $5\% - 12\%$ tự động khóa và tạo **Phiếu trình duyệt Trưởng phòng** (có nút phê duyệt trực tiếp trên giao diện). |

---

## 2. Cấu Trúc Thư Mục

```
d:\Download\XÂY AGENT\
├── agent\
│   └── workflow_engine.py    # Engine điều phối quy trình và các node xử lý
├── data\
│   ├── products.json         # Danh mục thiết bị, bảng giá hiện hành & tồn kho
│   ├── policies.json         # Quy định hạn mức chiết khấu & SLA
│   ├── sales_team.json       # Danh sách 6 NVKD & tình trạng tải công việc
│   └── pipeline_db.json      # Cơ sở dữ liệu lưu các hồ sơ cơ hội CRM
├── static\
│   └── index.html            # Giao diện Web tương tác Localhost đầy đủ tính năng
├── test_scenarios.py         # Bộ test 4 kịch bản tự động
├── server.py                 # Máy chủ HTTP Web & API RESTful (Port 8000)
├── run_localhost.bat         # File kích hoạt 1-click cho Windows
└── README.md
```

---

## 3. Cách Khởi Động Trên Localhost

### Cách 1: Chạy bằng file `.bat` (Khuyên dùng)
Nhấp đúp chuột vào file **`run_localhost.bat`**.

### Cách 2: Chạy bằng dòng lệnh (Terminal / PowerShell)
Tại thư mục `d:\Download\XÂY AGENT`, chạy lệnh:
```bash
uv run python server.py
# hoặc
python server.py
```

Sau khi server khởi động, mở trình duyệt truy cập:
👉 **`http://localhost:8000`**

---

## 4. Các Kịch Bản Thử Nghiệm Có Sẵn Trên Giao Diện

1. **Ca 1 (Thiếu thông tin)**: Khách hỏi chung chung không có số lượng, không email $\rightarrow$ Tự động sinh Email yêu cầu bổ sung.
2. **Ca 2 (Đầy đủ & Chuẩn thẩm quyền)**: Mua 5 laptop + 1 switch, chiết khấu 4%, kho có sẵn $\rightarrow$ Lập báo giá & Email phản hồi gửi ngay.
3. **Ca 3 (Vượt thẩm quyền - Chiết khấu 10%)**: Mua máy chủ + laptop, đòi chiết khấu 10% $\rightarrow$ Chuyển Trưởng phòng duyệt (có nút duyệt trên màn hình).
4. **Ca 4 (Rủi ro thời hạn & Kho)**: Cần gấp 2 máy chủ Dell trong 3 ngày nhưng kho hết hàng (lead time 25 ngày) $\rightarrow$ Cảnh báo rủi ro và đề xuất giao 2 đợt.

