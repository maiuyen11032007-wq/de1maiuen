import os
import json
import urllib.request
import urllib.error
from typing import Dict, Any, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_FILE = os.path.join(BASE_DIR, ".env")

def get_gemini_api_key() -> Optional[str]:
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        return api_key.strip()
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("GEMINI_API_KEY="):
                    return line.strip().split("=", 1)[1].strip()
    return None

class GeminiAIAgent:
    def __init__(self, model_name: str = "gemini-2.5-flash"):
        self.api_key = get_gemini_api_key()
        self.model_name = model_name

    def call_gemini(self, prompt: str, system_instruction: Optional[str] = None, json_mode: bool = False) -> str:
        if not self.api_key:
            raise ValueError("Chưa cấu hình GEMINI_API_KEY")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"
        
        contents = [{"role": "user", "parts": [{"text": prompt}]}]
        body: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": 0.2 if json_mode else 0.5,
                "topP": 0.95
            }
        }
        
        if json_mode:
            body["generationConfig"]["responseMimeType"] = "application/json"

        if system_instruction:
            body["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }

        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text", "")
            return ""

    def extract_request_with_llm(self, raw_text: str, catalog_summary: str) -> Dict[str, Any]:
        """Dùng Gemini 2.5 Flash để bóc tách thông tin khách hàng từ văn bản tự do."""
        system_instruction = (
            "Bạn là Chuyên gia AI Phân tích Yêu cầu Bán hàng B2B của Công ty Công nghệ Minh An. "
            "Nhiệm vụ của bạn là đọc email/biểu mẫu của khách hàng, trích xuất chính xác các thực thể "
            "và đối chiếu với danh mục sản phẩm của công ty Minh An. "
            "Trả về DUY NHẤT một JSON hợp lệ tuân theo schema được yêu cầu."
        )

        prompt = f"""
Hãy phân tích yêu cầu mua hàng sau đây:
\"\"\"{raw_text}\"\"\"

Danh mục sản phẩm hiện có của Minh An:
{catalog_summary}

Yêu cầu xuất ra JSON chính xác với cấu trúc sau:
{{
  "customer_name": "Tên người gửi (hoặc Quý Khách hàng nếu chưa rõ)",
  "company_name": "Tên công ty / Doanh nghiệp (hoặc Doanh nghiệp chưa xác định)",
  "email": "Địa chỉ email (hoặc null)",
  "phone": "Số điện thoại (hoặc null)",
  "requested_deadline": "Thời hạn khách mong muốn bàn giao (hoặc null)",
  "budget": 0 (số tiền VND, hoặc null nếu không nhắc tới),
  "requested_discount_pct": 0.0 (phần trăm chiết khấu khách đề nghị, ví dụ 10.0),
  "items": [
    {{
      "raw_name": "Tên khách gọi",
      "matched_sku": "Mã SKU khớp nhất trong danh mục (hoặc null nếu không khớp)",
      "quantity": 1
    }}
  ],
  "missing_critical_info": ["Liệt kê các thông tin quan trọng bị thiếu (nếu có, ví dụ thiếu số lượng, thiếu email...)"]
}}
"""
        raw_res = self.call_gemini(prompt, system_instruction=system_instruction, json_mode=True)
        return json.loads(raw_res)

    def polish_response_email(
        self,
        customer_name: str,
        company_name: str,
        rep_name: str,
        rep_phone: str,
        rep_email: str,
        verified_items_summary: str,
        quote_summary: str,
        delivery_note: str
    ) -> str:
        """Dùng Gemini để viết email phản hồi khách hàng chuyên nghiệp, mượt mà."""
        system_instruction = (
            "Bạn là Trợ lý AI B2B của Công ty Công nghệ Minh An. Hãy viết một email chào giá và đề xuất giải pháp "
            "chuẩn mực doanh nghiệp, trang trọng, lịch sự, rõ ràng, không sai lệch bất kỳ số liệu đơn giá, thành tiền hay tiến độ nào."
        )

        prompt = f"""
Thông tin cơ hội bán hàng:
- Khách hàng: {customer_name} ({company_name})
- Chuyên viên phụ trách: {rep_name} (SĐT: {rep_phone}, Email: {rep_email})
- Chi tiết thiết bị & giá đã duyệt:
{verified_items_summary}
- Tổng kết giá trị:
{quote_summary}
- Ghi chú tiến độ giao hàng:
{delivery_note}

Hãy viết một email hoàn chỉnh (bao gồm lời chào, nội dung chi tiết, cam kết chất lượng, bảo hành, phương án tiến độ và thông tin liên hệ).
Chỉ trả về nội dung email, không thêm lời dẫn của bạn.
"""
        return self.call_gemini(prompt, system_instruction=system_instruction)

