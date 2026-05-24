# Thư mục Engine

## Tải Fairy-Stockfish

### Bước 1: Truy cập GitHub Releases

https://github.com/fairy-stockfish/Fairy-Stockfish/releases

### Bước 2: Chọn phiên bản

Tải phiên bản mới nhất cho Windows:

- Tìm file có tên dạng: `fairy-stockfish-largeboard_x86-64-*.zip`
- Hoặc: `fairy-stockfish_x86-64-*.zip`

### Bước 3: Giải nén

- Giải nén file .zip
- Tìm file `.exe` (thường là `fairy-stockfish.exe` hoặc tên tương tự)

### Bước 4: Copy vào thư mục này

- Đổi tên file thành `fairy-stockfish.exe`
- Copy vào thư mục `engine/` này

### Bước 5: Kiểm tra

Chạy lệnh sau để test:

```bash
cd engine
fairy-stockfish.exe
```

Gõ `quit` để thoát.

## Cấu trúc sau khi hoàn tất

```
engine/
├── fairy-stockfish.exe    # Engine chính
└── README.md              # File này
```

## Lưu ý

- File engine khá lớn (10-30 MB)
- Không commit file engine vào Git (đã có trong .gitignore)
- Mỗi người cần tải engine riêng
- Đảm bảo file có quyền execute (trên Linux/Mac)

## Các engine khác (tùy chọn)

Ngoài Fairy-Stockfish, bạn có thể thử:

- **Pikafish**: https://github.com/official-pikafish/Pikafish
- **Stockfish variants**: Một số fork hỗ trợ Xiangqi

Lưu ý: Code hiện tại được viết cho Fairy-Stockfish, cần điều chỉnh nếu dùng engine khác.

## Xử lý lỗi

### Lỗi: "File not found"

- Kiểm tra file `fairy-stockfish.exe` có trong thư mục này không
- Kiểm tra tên file có đúng không (phân biệt hoa thường)

### Lỗi: "Permission denied" (Linux/Mac)

```bash
chmod +x fairy-stockfish
```

### Lỗi: Engine không chạy

- Thử chạy trực tiếp file engine để xem lỗi
- Kiểm tra phiên bản Windows (32-bit vs 64-bit)
- Tải lại file engine

## Thông tin thêm

- **Website**: https://fairy-stockfish.github.io/
- **GitHub**: https://github.com/fairy-stockfish/Fairy-Stockfish
- **Documentation**: https://github.com/fairy-stockfish/Fairy-Stockfish/wiki
