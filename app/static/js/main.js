/**
 * PhotoEfas - 前端交互脚本
 */

// 自动隐藏flash消息
document.addEventListener('DOMContentLoaded', () => {
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.transition = 'opacity 0.5s';
            alert.style.opacity = '0';
            setTimeout(() => alert.remove(), 500);
        }, 5000);
    });

    // 文件上传前端验证
    document.querySelectorAll('input[type="file"]').forEach(input => {
        input.addEventListener('change', () => {
            const file = input.files[0];
            if (!file) return;

            const allowed = ['image/png', 'image/jpeg', 'image/bmp'];
            if (!allowed.includes(file.type)) {
                alert('仅支持 PNG / JPG / BMP 格式的图片文件');
                input.value = '';
                return;
            }

            // 检查文件扩展名（防 double extension 攻击）
            const name = file.name.toLowerCase();
            const ext = name.split('.').pop();
            if (!['png', 'jpg', 'jpeg', 'bmp'].includes(ext)) {
                alert('文件扩展名不合法');
                input.value = '';
                return;
            }

            // 文件大小限制 16MB
            if (file.size > 16 * 1024 * 1024) {
                alert('文件大小不能超过 16MB');
                input.value = '';
            }
        });
    });
});
