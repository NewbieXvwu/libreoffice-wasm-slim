/* -*- Mode: JS; tab-width: 2; indent-tabs-mode: nil; js-indent-level: 2; fill-column: 100 -*- */
// SPDX-License-Identifier: MIT
// 改编自 zetajs 官方 convertpdf 示例（allotropia/zetajs, MIT）。
// 在 LOWA 线程内运行：加载 /tmp/fixture.docx 并导出 PDF 到 /tmp/output.pdf。
import { ZetaHelperThread } from './assets/vendor/zetajs/zetaHelper.js';

const zHT = new ZetaHelperThread();
const zetajs = zHT.zetajs;
const css = zHT.css;

let xModel;

function run() {
  const bean_hidden = new css.beans.PropertyValue({Name: 'Hidden', Value: true});
  const bean_overwrite = new css.beans.PropertyValue({Name: 'Overwrite', Value: true});
  const bean_pdf_export = new css.beans.PropertyValue({Name: 'FilterName', Value: 'writer_pdf_Export'});

  zHT.thrPort.onmessage = (e) => {
    if (e.data.cmd !== 'convert') throw Error('未知命令: ' + e.data.cmd);
    try {
      if (xModel !== undefined &&
          xModel.queryInterface(zetajs.type.interface(css.util.XCloseable))) {
        xModel.close(false);
      }
      xModel = zHT.desktop.loadComponentFromURL('file://' + e.data.from, '_blank', 0, [bean_hidden]);
      xModel.storeToURL('file://' + e.data.to, [bean_overwrite, bean_pdf_export]);
      zetajs.mainPort.postMessage({cmd: 'converted', from: e.data.from, to: e.data.to});
    } catch (err) {
      let message = String(err);
      try { message = zetajs.catchUnoException(err).Message || message; } catch (_) {}
      zetajs.mainPort.postMessage({cmd: 'error', message});
    }
  };

  zHT.thrPort.postMessage({cmd: 'start'});
}

run();
