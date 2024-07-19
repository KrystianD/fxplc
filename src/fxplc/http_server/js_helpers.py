import json

from nicegui import ui


def js_copy_handler(text):
    return f'() => setTimeout(()=>{{unsecuredCopyToClipboard({json.dumps(text)})}}, 1)'


def add_custom_json():
    ui.add_head_html("""<script>
function unsecuredCopyToClipboard(text) {
  const textArea = document.createElement("textarea");
  textArea.value = text;
  document.body.appendChild(textArea);
  textArea.focus({preventScroll: true});
  textArea.select();
  try {
    document.execCommand('copy');
  } catch (err) {
    console.error('Unable to copy to clipboard', err);
  }
  document.body.removeChild(textArea);
}
</script>;""")
