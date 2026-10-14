(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x263 (bvshl y (_ bv24 32))))
(let ((?x259 (bvshl x (_ bv24 32))))
(let ((?x266 (bvsub ?x259 ?x263)))
(let ((?x24 (bvsub x y)))
(let ((?x265 (bvshl ?x24 (_ bv24 32))))
(and (distinct ?x265 ?x266) true)))))))
(check-sat)
