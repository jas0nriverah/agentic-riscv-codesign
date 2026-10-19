(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x83 (bvmul x (_ bv16 32))))
(let ((?x81 (bvshl x (_ bv4 32))))
(and (distinct ?x81 ?x83) true))))
(check-sat)
