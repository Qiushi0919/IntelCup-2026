const authorWechatDialog = document.getElementById('author-wechat-dialog');
document.getElementById('author-wechat-button').addEventListener('click', () => {
  authorWechatDialog.showModal();
});
authorWechatDialog.addEventListener('keydown', event => {
  if (event.key === 'Escape') authorWechatDialog.close();
});
authorWechatDialog.addEventListener('click', event => {
  if (event.target !== authorWechatDialog) return;
  const bounds = authorWechatDialog.getBoundingClientRect();
  if (event.clientX < bounds.left || event.clientX > bounds.right ||
      event.clientY < bounds.top || event.clientY > bounds.bottom) {
    authorWechatDialog.close();
  }
});
