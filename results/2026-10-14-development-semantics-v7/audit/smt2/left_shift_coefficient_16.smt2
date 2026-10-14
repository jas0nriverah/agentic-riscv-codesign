(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x189 (bvmul x (_ bv65536 32))))
(let ((?x187 (bvshl x (_ bv16 32))))
(and (distinct ?x187 ?x189) true))))
(check-sat)
