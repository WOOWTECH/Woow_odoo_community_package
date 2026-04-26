/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const visitorBusService = {
    dependencies: ["bus_service", "notification", "action"],
    start(env, { bus_service, notification, action }) {
        bus_service.subscribe("community_visitor/visit_update", (payload) => {
            const { visitor_name, unit_name, event, visit_id } = payload;

            let message = "";
            let type = "info";

            switch (event) {
                case "confirmed":
                    message = `住戶已確認放行：${visitor_name}（${unit_name}）`;
                    type = "success";
                    break;
                case "rejected":
                    message = `住戶已拒絕：${visitor_name}（${unit_name}）`;
                    type = "danger";
                    break;
                case "timeout":
                    message = `等待逾時：${visitor_name}（${unit_name}）`;
                    type = "warning";
                    break;
            }

            notification.add(message, {
                title: "訪客通知",
                type: type,
                sticky: event !== "confirmed",
            });
        });
    },
};

registry.category("services").add("visitor_bus_service", visitorBusService);
