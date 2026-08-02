import QtQuick 2.15

Item {
    id: root
    width: 220
    height: 42

    property int index: 0
    property alias model: repeater.model
    property color fieldColor: "#11161d"
    property color borderColor: "#21262d"
    property color focusColor: "#58a6ff"
    property color hoverColor: "#232b36"
    property color menuColor: "#151b24"
    property color textColor: "#f0f6fc"
    property font font
    property int radius: 10
    property bool open: false

    signal valueChanged(int id)

    // dropdown - opens upward
    Column {
        id: dropDown
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: field.top
        anchors.bottomMargin: 6
        visible: root.open
        spacing: 3
        z: 500

        Repeater {
            id: repeater

            delegate: Rectangle {
                width: dropDown.width
                height: 36
                radius: 7
                color: root.index === index ? "#1c2530" : root.menuColor
                border.color: root.index === index ? root.focusColor : root.borderColor
                border.width: 1

                Text {
                    anchors.left: parent.left
                    anchors.leftMargin: 12
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.right: parent.right
                    anchors.rightMargin: 12
                    text: model.name
                    color: root.textColor
                    font: root.font
                    elide: Text.ElideRight
                }

                MouseArea {
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        root.index = index
                        root.open = false
                        root.valueChanged(index)
                    }
                }
            }
        }
    }

    // field
    Rectangle {
        id: field
        anchors.fill: parent
        radius: root.radius
        color: root.fieldColor
        border.color: root.open ? root.focusColor : root.borderColor
        border.width: 1
        Behavior on border.color { ColorAnimation { duration: 200 } }

        // current selection text, via the same role mechanism as the dropdown
        Repeater {
            id: fieldRepeater
            model: repeater.model
            delegate: Text {
                visible: index === root.index
                anchors.left: field.left
                anchors.leftMargin: 14
                anchors.right: field.right
                anchors.rightMargin: 30
                anchors.verticalCenter: field.verticalCenter
                text: model.name
                color: root.textColor
                font: root.font
                elide: Text.ElideRight
            }
        }

        Text {
            anchors.right: parent.right
            anchors.rightMargin: 12
            anchors.verticalCenter: parent.verticalCenter
            text: root.open ? "▴" : "▾"
            color: "#6e7681"
            font.pixelSize: 12
        }

        MouseArea {
            anchors.fill: parent
            cursorShape: Qt.PointingHandCursor
            onClicked: root.open = !root.open
        }
    }
}
