(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x127 (bvmul x (_ bv512 32))))
(let ((?x125 (bvshl x (_ bv9 32))))
(and (distinct ?x125 ?x127) true))))
(check-sat)
