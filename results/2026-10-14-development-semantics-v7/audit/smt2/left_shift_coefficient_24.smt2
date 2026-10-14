(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x261 (bvmul x (_ bv16777216 32))))
(let ((?x259 (bvshl x (_ bv24 32))))
(and (distinct ?x259 ?x261) true))))
(check-sat)
