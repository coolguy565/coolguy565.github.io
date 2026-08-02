import QtQuick 2.15
import SddmComponents 2.0

Rectangle {
    id: root
    width: Screen.width
    height: Screen.height
    color: "#0b0f14"

    property color accent: "#58a6ff"

    // background gradient
    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.0; color: "#111827" }
            GradientStop { position: 0.55; color: "#0b0f14" }
            GradientStop { position: 1.0; color: "#05070a" }
        }
    }

    // soft glow behind the avatar
    Rectangle {
        id: glow
        anchors.centerIn: parent
        anchors.verticalCenterOffset: -40
        width: 420
        height: 420
        radius: width / 2
        color: accent
        opacity: 0.06
    }

    // clock - top center
    Text {
        id: clockText
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        anchors.topMargin: 34
        color: "#c9d1d9"
        font.family: "Noto Sans, DejaVu Sans, sans-serif"
        font.pixelSize: 20
        font.letterSpacing: 6
        font.weight: Font.Light
        text: "00:00"
        opacity: 0.9
    }
    Timer {
        interval: 1000
        running: true
        repeat: true
        onTriggered: clockText.text = Qt.formatTime(new Date(), "HH:mm")
    }

    // center block
    Column {
        id: centerBox
        anchors.centerIn: parent
        width: 340
        spacing: 18
        opacity: 0
        transform: Translate { id: slide; y: 12 }
        Behavior on opacity { NumberAnimation { duration: 500; easing.type: Easing.OutCubic } }
        Behavior on transform { NumberAnimation { duration: 500; easing.type: Easing.OutCubic } }

        // avatar
        Rectangle {
            id: avatarRing
            anchors.horizontalCenter: parent.horizontalCenter
            width: 176
            height: 176
            radius: width / 2
            color: "#151b24"
            border.width: 2
            border.color: "#2a3441"
            clip: true

            Image {
                id: avatar
                anchors.fill: parent
                anchors.margins: 16
                source: "avatar.png"
                fillMode: Image.PreserveAspectFit
                sourceSize.width: 176
                sourceSize.height: 176
            }

            // accent ring highlight
            Rectangle {
                anchors.fill: parent
                radius: width / 2
                color: "transparent"
                border.width: 2
                border.color: accent
                opacity: 0.0
                Behavior on opacity { NumberAnimation { duration: 300 } }
            }
        }

        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: userModel.lastUser
            color: "#f0f6fc"
            font.family: "Noto Sans, DejaVu Sans, sans-serif"
            font.pixelSize: 28
            font.weight: Font.DemiBold
            font.letterSpacing: 1
        }

        // password box with placeholder
        Item {
            anchors.horizontalCenter: parent.horizontalCenter
            width: 320
            height: 50

            PasswordBox {
                id: passwordBox
                anchors.fill: parent
                radius: 10
                focus: true
                color: "#11161d"
                borderColor: "#21262d"
                focusColor: accent
                hoverColor: "#232b36"
                textColor: "#f0f6fc"
                font.family: "Noto Sans, DejaVu Sans, sans-serif"
                font.pixelSize: 16
                Keys.onReturnPressed: login()
            }

            Text {
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                anchors.leftMargin: 16
                text: "Password"
                color: "#6e7681"
                font.pixelSize: 14
                visible: passwordBox.text.length === 0 && !passwordBox.activeFocus
            }
        }
    }

    // branding - bottom center
    Text {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 26
        text: "Cool Arch"
        color: accent
        font.family: "Noto Sans, DejaVu Sans, sans-serif"
        font.pixelSize: 14
        font.weight: Font.DemiBold
        font.letterSpacing: 4
        opacity: 0.5
    }

    // session selector - bottom left
    CoolCombo {
        id: sessionCombo
        anchors.left: parent.left
        anchors.bottom: parent.bottom
        anchors.margins: 20
        width: 220
        height: 42
        model: sessionModel
        index: sessionModel.lastIndex
        font.family: "Noto Sans, DejaVu Sans, sans-serif"
        font.pixelSize: 13
    }

    // power buttons - bottom right
    Row {
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: 20
        spacing: 14

        Rectangle {
            id: rebootWrap
            width: 48
            height: 48
            radius: 24
            color: "#11161d"
            border.color: rebootButton.isFocused ? accent : "#21262d"
            border.width: 1
            Behavior on border.color { ColorAnimation { duration: 200 } }

            ImageButton {
                id: rebootButton
                anchors.centerIn: parent
                width: 24
                height: 24
                source: "restart.svg"
                onClicked: sddm.reboot()
            }
        }

        Rectangle {
            id: shutdownWrap
            width: 48
            height: 48
            radius: 24
            color: "#11161d"
            border.color: shutdownButton.isFocused ? "#f85149" : "#21262d"
            border.width: 1
            Behavior on border.color { ColorAnimation { duration: 200 } }

            ImageButton {
                id: shutdownButton
                anchors.centerIn: parent
                width: 24
                height: 24
                source: "power.svg"
                onClicked: sddm.powerOff()
            }
        }
    }

    Component.onCompleted: {
        centerBox.opacity = 1
        slide.y = 0
    }

    function login() {
        sddm.login(userModel.lastUser, passwordBox.text, sessionCombo.index)
    }
}
