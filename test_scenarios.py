import json
from agent.workflow_engine import MinhAnWorkflowEngine

def run_tests():
    engine = MinhAnWorkflowEngine()

    print("==================================================")
    print("TEST 1: YÊU CẦU THIẾU THÔNG TIN (INCOMPLETE INFO)")
    print("==================================================")
    text1 = """
    Chào Minh An,
    Công ty mình ở Cầu Giấy đang chuẩn bị chuyển văn phòng mới nên có nhu cầu mua sắm thêm một số máy tính làm việc cho nhân viên và thiết bị mạng. 
    Nhờ Minh An gửi giúp mình báo giá các dòng máy tính tốt và chi phí triển khai nhé. Cảm ơn!
    """
    res1 = engine.process_request(text1)
    print(f"Status Code: {res1['status_code']}")
    print(f"Missing Fields: {res1['extracted_data']['missing_fields']}")
    assert res1['status_code'] == 'CLARIFICATION_REQUIRED', "Test 1 failed!"
    print("=> Test 1 PASSED: Tự động kích hoạt nhánh Yêu cầu KH làm rõ/bổ sung!\n")

    print("==================================================")
    print("TEST 2: ĐỦ THÔNG TIN & TRONG THẨM QUYỀN (4% CHIẾT KHẤU)")
    print("==================================================")
    text2 = """
    Kính gửi: Bộ phận Kinh doanh - Công ty Công nghệ Minh An,
    Tôi là Nguyễn Tuấn Anh, Trưởng phòng IT Công ty Cổ phần Alpha Logistics (email: tuananh@alphalogistics.vn, SĐT: 0988.123.456).
    Công ty chúng tôi cần mua thiết bị bổ sung cho phòng vận hành bao gồm:
    - 5 chiếc Laptop Dell Latitude 5520
    - 1 Thiết bị Switch Cisco Catalyst 9200L 24 Ports
    - 1 Gói Dịch vụ lắp đặt cấu hình mạng nội bộ
    Thời hạn hoàn thành: Trong vòng 7 ngày tới.
    Ngân sách dự kiến: Khoảng 150 triệu VND.
    Do đây là đơn hàng đầu tiên hợp tác, đề nghị Minh An hỗ trợ chiết khấu 4% trên tổng giá trị niêm yết.
    Rất mong nhận được phản hồi sớm. Trân trọng cảm ơn!
    """
    res2 = engine.process_request(text2)
    print(f"Status Code: {res2['status_code']}")
    print(f"Assigned Rep: {res2['assigned_rep_name']}")
    print(f"Total Quoted Price: {res2['total_amount']:,.0f} VND")
    print(f"Requires Approval: {res2['opportunity_profile']['pricing_policy']['requires_manager_approval']}")
    assert res2['status_code'] == 'READY_TO_SEND', "Test 2 failed!"
    print("=> Test 2 PASSED: Đủ thông tin, giá chuẩn hiện hành, tự động sinh báo giá gửi ngay!\n")

    print("==================================================")
    print("TEST 3: VƯỢT THẨM QUYỀN (10% CHIẾT KHẤU -> TRƯỞNG PHÒNG DUYỆT)")
    print("==================================================")
    text3 = """
    Kính gửi Công ty Minh An,
    Tôi là Lê Thu Hương - Phụ trách Mua sắm Tập đoàn SmartRetail (email: huong.le@smartretail.com.vn, SĐT: 0918.999.888).
    Chúng tôi chuẩn bị mở rộng thêm 2 chi nhánh bán lẻ và cần trang bị hạ tầng CNTT gồm:
    - 10 chiếc Laptop Dell Latitude
    - 2 bộ phát WiFi chuyên dụng Aruba
    - 1 Máy chủ HPE ProLiant DL380 Gen10
    - 1 Gói Dịch vụ cài đặt máy chủ
    Thời hạn bàn giao: Trong vòng 15 ngày làm việc.
    Ngân sách nội bộ được duyệt: 350 triệu VND.
    Do số lượng hạng mục nhiều và tiềm năng ký hợp đồng bảo trì lâu dài, chúng tôi yêu cầu mức chiết khấu 10% trên bảng giá niêm yết.
    Đề nghị Minh An phản hồi và gửi bản chào giá chính thức trong hôm nay.
    """
    res3 = engine.process_request(text3)
    print(f"Status Code: {res3['status_code']}")
    print(f"Requires Manager Approval: {res3['opportunity_profile']['pricing_policy']['requires_manager_approval']}")
    print(f"Approval Reasons: {res3['opportunity_profile']['pricing_policy']['approval_reasons']}")
    assert res3['status_code'] == 'PENDING_APPROVAL', "Test 3 failed!"
    print("=> Test 3 PASSED: Phát hiện chiết khấu 10% vượt quyền 5% -> Trình Trưởng phòng duyệt!\n")

    print("==================================================")
    print("TEST 4: XUNG ĐỘT THỜI HẠN & HẾT KHO (RỦI RO TIẾN ĐỘ)")
    print("==================================================")
    text4 = """
    Kính gửi Minh An Tech,
    Tôi là Phạm Quốc Dũng - Giám đốc Công nghệ Công ty Fintech Findex (email: dung.pham@findex.vn, SĐT: 0903.111.222).
    Hệ thống trung tâm dữ liệu của chúng tôi cần mở rộng khẩn cấp:
    - 2 Máy chủ Dell PowerEdge R750
    - 1 Thiết bị tường lửa Fortinet FortiGate 60F
    Yêu cầu tiến độ: Bắt buộc giao hàng và hoàn tất lắp đặt trong vòng 3 ngày tới!
    Đề nghị chiết khấu 5%. Xin cảm ơn.
    """
    res4 = engine.process_request(text4)
    audit4 = res4['opportunity_profile']['inventory_audit']
    print(f"Deadline Feasible: {audit4['is_deadline_feasible']}")
    print(f"Deadline Warning: {audit4['deadline_warning']}")
    assert not audit4['is_deadline_feasible'], "Test 4 failed!"
    print("=> Test 4 PASSED: Phát hiện kho hết hàng (lead time 25 ngày) vs KH đòi 3 ngày -> Cảnh báo & đề xuất chia đợt!\n")

    print("TẤT CẢ 4 KỊCH BẢN ĐÃ TEST THÀNH CÔNG 100%!")

if __name__ == "__main__":
    run_tests()

