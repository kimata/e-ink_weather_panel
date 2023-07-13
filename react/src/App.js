import "./App.css";
import "bootstrap/dist/css/bootstrap.min.css";
import { Github } from "react-bootstrap-icons";

import { TransformWrapper, TransformComponent } from "react-zoom-pan-pinch";
import { useState, useEffect } from "react";
import Select from "react-select";
import * as Scroll from "react-scroll";

function App() {
    const MODE_OPTION_LIST = [
        { value: "normal", label: "BOOX Mira Pro" },
        { value: "small", label: "BOOX Mira" },
    ];

    const DEFAULT_IMAGE = "gray.png";
    const API_ENDPOINT = "/weather_panel/api";
    const [mode, setMode] = useState(MODE_OPTION_LIST[0]);
    const [imageSrc, setImageSrc] = useState(DEFAULT_IMAGE);
    const [finish, setFinish] = useState(true);
    const [error, setError] = useState(false);
    const [errorMessage, setErrorMessage] = useState("");
    const [log, setLog] = useState([]);

    const scroller = Scroll.scroller;
    var Element = Scroll.Element;

    const reqGenerate = () => {
        return new Promise((resolve, reject) => {
            const query = new URLSearchParams({ mode: mode.value });
            fetch(API_ENDPOINT + "/run?" + query)
                .then((res) => res.json())
                .then((resJson) => resolve(resJson))
                .catch((error) => {
                    setError(true);
                    setErrorMessage("通信に失敗しました");
                    console.error(error);
                });
        });
    };

    const readImage = (token) => {
        return new Promise((resolve, reject) => {
            const param = new URLSearchParams({ token: token });
            fetch(API_ENDPOINT + "/image", {
                method: "POST",
                body: param,
            })
                .then((res) => res.blob())
                .then((resBlob) => {
                    setImageSrc(URL.createObjectURL(resBlob));
                })
                .catch((error) => {
                    setError(true);
                    setErrorMessage(error);
                    console.error("通信に失敗しました", error);
                });
        });
    };

    const generate = async () => {
        let res = await reqGenerate();
        setFinish(false);
        setError(false);
        setLog([]);
        setImageSrc(DEFAULT_IMAGE);
        readLog(res.token);
    };

    useEffect(() => {
        scroller.scrollTo("logEnd", {
            smooth: true,
            containerId: "log",
        });
    }, [log, scroller]);

    const readLog = async (token) => {
        const decoder = new TextDecoder();
        const param = new URLSearchParams({ token: token });
        fetch(API_ENDPOINT + "/log", {
            method: "POST",
            body: param,
        })
            .then((res) => res.body.getReader())
            .then((reader) => {
                function processChunk({ done, value }) {
                    if (done) {
                        readImage(token);
                        setFinish(true);
                        return;
                    }
                    let lines = decoder.decode(value).trimEnd().split(/\n/);
                    setLog((old) => old.concat(lines));

                    reader.read().then(processChunk);
                }
                reader.read().then(processChunk);
            });
    };

    const GenerateButton = () => {
        if (finish) {
            return (
                <button className="btn btn-primary w-auto" type="button" data-testid="button" onClick={generate}>
                    生成
                </button>
            );
        } else {
            return (
                <button className="btn btn-primary w-auto" type="button" disabled>
                    <span className="spinner-border spinner-border-sm me-3" role="status" aria-hidden="true" />
                    生成中...
                </button>
            );
        }
    };

    const LogData = () => {
        if (error) {
            return <span>{errorMessage}</span>;
        }
        return log.map((line, index) => (
            <span>
                {line}
                <br />
            </span>
        ));
    };

    return (
        <div className="App text-start">
            <div className="d-flex flex-column flex-md-row align-items-center p-3 px-md-4 mb-3 bg-white border-bottom shadow-sm">
                <h1 className="display-6 my-0 mr-md-auto font-weight-normal">気象パネル画像</h1>
            </div>

            <div className="container">
                <div className="row">
                    <div className="col-12">
                        <label htmlFor="mode" className="me-2">
                            モード:
                        </label>
                        <Select
                            options={MODE_OPTION_LIST}
                            defaultValue={MODE_OPTION_LIST[0]}
                            onChange={setMode}
                            className="mb-2"
                            id="mode"
                        />
                        <GenerateButton />
                    </div>
                </div>

                <div className="row mt-4">
                    <h2>ログ</h2>
                    <div className="container">
                        <div
                            className="col-12 overflow-scroll ms-2 shadow p-3 bg-body rounded"
                            style={{ height: 10 + "em" }}
                            data-testid="log"
                            id="log"
                        >
                            <small>
                                <LogData />
                                <Element name="logEnd"></Element>
                            </small>
                        </div>
                    </div>
                </div>

                <div className="row mt-5">
                    <h2>生成画像</h2>
                    <div className="container">
                        <div className="col-12 ms-2 shadow bg-body rounded">
                            <TransformWrapper>
                                <TransformComponent>
                                    <img
                                        src={imageSrc}
                                        width="3200"
                                        alt="生成された画像"
                                        data-testid="image"
                                        className="ratio ratio-16x9 img-fluid img-rounded"
                                    />
                                </TransformComponent>
                            </TransformWrapper>
                        </div>
                    </div>
                </div>

                <div className="row mt-2">
                    <div className="p-1 float-end text-end">
                        <p className="display-6">
                            <a href="https://github.com/kimata/e-ink_weather_panel/" className="text-secondary">
                                <Github />
                            </a>
                        </p>
                    </div>
                </div>
            </div>
        </div>
    );
}

export default App;
