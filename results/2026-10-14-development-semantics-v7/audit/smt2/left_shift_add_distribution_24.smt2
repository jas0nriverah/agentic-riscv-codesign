(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x263 (bvshl y (_ bv24 32))))
(let ((?x259 (bvshl x (_ bv24 32))))
(let ((?x264 (bvadd ?x259 ?x263)))
(let ((?x19 (bvadd x y)))
(let ((?x262 (bvshl ?x19 (_ bv24 32))))
(and (distinct ?x262 ?x264) true)))))))
(check-sat)
